"""Agente de devoluciones de EcoMarket construido con LangChain (`create_agent`).

Conecta las piezas del proyecto:

    mensaje ──► AgenteDevoluciones.responder()
                  │  guardas de entrada (vacío, longitud)
                  ▼
                create_agent (LangGraph)
                  ├─ LLM con tool calling (Ollama o API compatible con OpenAI)
                  ├─ herramientas: RAG del Taller 2 + pedido + elegibilidad + etiqueta + escalamiento
                  ├─ middleware: límite de llamadas al modelo y a herramientas por turno,
                  │              guarda contra acciones anunciadas pero no ejecutadas
                  └─ checkpointer: memoria de la conversación por thread_id
                  ▼
                RespuestaAgente (texto + pasos ejecutados) ──► CLI / interfaz web
                  │
                  └─ callbacks de auditoría ──► logs/auditoria.jsonl

Si el LLM no responde (servicio caído, timeout), el mensaje al cliente sale
de este módulo, no del modelo.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field

import httpx
import openai
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from src import llm
from src.agente.guardas import GuardiaAccionesInventadas
from src.agente.herramientas import HERRAMIENTAS
from src.agente.observabilidad import Auditoria, enmascarar, fijar_contexto, registrar
from src.agente.prompts_agente import construir_system_prompt
from src.agente.reglas import fecha_referencia

log = logging.getLogger(__name__)

AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", "ollama")
AGENT_MODEL = os.getenv("AGENT_MODEL", "qwen2.5:7b")
# Ollama recorta el contexto a 4.096 tokens si no se indica otro valor; el
# prompt, los esquemas de las herramientas y el historial superan ese límite.
AGENT_NUM_CTX = int(os.getenv("AGENT_NUM_CTX", "8192"))
AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT", "600"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", llm.BASE_URL.removesuffix("/v1"))

MAX_CARACTERES = 2000
LIMITE_LLAMADAS_MODELO = 8
LIMITE_LLAMADAS_HERRAMIENTAS = 6

MENSAJE_VACIO = "¡Hola! Soy Eco, el asistente de EcoMarket. ¿En qué te puedo ayudar?"
MENSAJE_MUY_LARGO = (
    "Tu mensaje es un poco largo para procesarlo. ¿Me lo puedes resumir en pocas líneas? "
    "Si tienes un número de pedido, inclúyelo."
)
MENSAJE_SIN_SERVICIO = (
    "Lo siento, en este momento no puedo procesar tu solicitud porque uno de nuestros "
    "sistemas no está respondiendo. Inténtalo de nuevo en unos minutos o escríbenos de "
    "lunes a sábado, de 7:00 a. m. a 8:00 p. m., para que un asesor te atienda."
)
MENSAJE_ERROR = (
    "Lo siento, ocurrió un problema inesperado al atender tu solicitud. ¿Quieres que te "
    "comunique con un asesor?"
)
MENSAJE_SIN_RESPUESTA = (
    "No logré completar tu solicitud en este momento. ¿Quieres que te comunique con un "
    "asesor para revisarla?"
)

ERRORES_DE_CONEXION = (
    httpx.ConnectError,
    httpx.TimeoutException,
    openai.APIConnectionError,
    openai.APITimeoutError,
    ConnectionError,
    TimeoutError,
)


@dataclass
class PasoHerramienta:
    """Una llamada a herramienta dentro de un turno: lo que pidió el LLM y lo que obtuvo."""

    nombre: str
    argumentos: dict
    resultado: dict

    @property
    def status(self) -> str | None:
        return self.resultado.get("status")


@dataclass
class RespuestaAgente:
    texto: str
    pasos: list[PasoHerramienta] = field(default_factory=list)
    trace_id: str = ""
    latencia_ms: int = 0
    error: str | None = None

    @property
    def herramientas(self) -> list[str]:
        return [paso.nombre for paso in self.pasos]

    @property
    def etiquetas(self) -> list[str]:
        """Rutas de las etiquetas PDF generadas en el turno (para ofrecer la descarga)."""
        return [
            paso.resultado["label_file"]
            for paso in self.pasos
            if paso.status == "SUCCESS" and paso.resultado.get("label_file")
        ]


def crear_modelo(nombre: str | None = None) -> BaseChatModel:
    """LLM del agente, temperatura 0 para que las decisiones sean reproducibles.

    Con `AGENT_PROVIDER=ollama` se usa el cliente nativo de Ollama para poder
    fijar `num_ctx`; con `openai` sirve cualquier API compatible (OpenAI, Groq,
    vLLM) configurada con `LLM_BASE_URL` y `LLM_API_KEY`, como en los talleres.
    """
    nombre = nombre or AGENT_MODEL
    if AGENT_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=nombre,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
            num_ctx=AGENT_NUM_CTX,
            keep_alive="30m",
            client_kwargs={"timeout": AGENT_TIMEOUT},
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=nombre,
        base_url=llm.BASE_URL,
        api_key=llm.API_KEY,
        temperature=0,
        timeout=AGENT_TIMEOUT,
        max_retries=1,
    )


class AgenteDevoluciones:
    """Agente con memoria por conversación (`thread_id`)."""

    def __init__(self, modelo: str | None = None, modelo_chat: BaseChatModel | None = None):
        """`modelo_chat` permite inyectar un modelo simulado en las pruebas unitarias."""
        self.modelo = modelo or AGENT_MODEL
        self.grafo = create_agent(
            model=modelo_chat or crear_modelo(self.modelo),
            tools=HERRAMIENTAS,
            system_prompt=construir_system_prompt(fecha_referencia()),
            middleware=[
                ModelCallLimitMiddleware(run_limit=LIMITE_LLAMADAS_MODELO, exit_behavior="end"),
                ToolCallLimitMiddleware(run_limit=LIMITE_LLAMADAS_HERRAMIENTAS, exit_behavior="end"),
                GuardiaAccionesInventadas(),
            ],
            checkpointer=InMemorySaver(),
        )

    def historial(self, thread_id: str) -> list:
        estado = self.grafo.get_state({"configurable": {"thread_id": thread_id}})
        return estado.values.get("messages", []) if estado else []

    def responder(self, mensaje: str, thread_id: str) -> RespuestaAgente:
        """Procesa un mensaje del cliente dentro de la conversación `thread_id`."""
        inicio = time.perf_counter()
        trace_id = uuid.uuid4().hex[:12]
        mensaje = (mensaje or "").strip()
        fijar_contexto(trace_id=trace_id, thread_id=thread_id)

        if not mensaje:
            return RespuestaAgente(texto=MENSAJE_VACIO, trace_id=trace_id)
        if len(mensaje) > MAX_CARACTERES:
            registrar("turn_rejected", trace_id=trace_id, thread_id=thread_id, reason="mensaje_muy_largo")
            return RespuestaAgente(texto=MENSAJE_MUY_LARGO, trace_id=trace_id)

        auditoria = Auditoria(thread_id=thread_id, trace_id=trace_id, modelo=self.modelo)
        registrar("turn_start", trace_id=trace_id, thread_id=thread_id, message=enmascarar(mensaje))
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [auditoria],
            "recursion_limit": 30,
        }

        previos = len(self.historial(thread_id))
        try:
            resultado = self.grafo.invoke({"messages": [HumanMessage(mensaje)]}, config)
        except ERRORES_DE_CONEXION as excepcion:
            return self._fallo(MENSAJE_SIN_SERVICIO, excepcion, trace_id, thread_id, inicio)
        except Exception as excepcion:  # noqa: BLE001 — el cliente nunca ve una traza
            log.exception("Error del agente")
            return self._fallo(MENSAJE_ERROR, excepcion, trace_id, thread_id, inicio)

        nuevos = resultado["messages"][previos:]
        pasos = extraer_pasos(nuevos)
        texto = texto_final(nuevos) or MENSAJE_SIN_RESPUESTA
        latencia = round((time.perf_counter() - inicio) * 1000)
        registrar(
            "turn_end",
            trace_id=trace_id,
            thread_id=thread_id,
            model=self.modelo,
            tools=[p.nombre for p in pasos],
            statuses=[p.status for p in pasos],
            input_tokens=auditoria.tokens["input"],
            output_tokens=auditoria.tokens["output"],
            latency_ms=latencia,
        )
        return RespuestaAgente(texto=texto, pasos=pasos, trace_id=trace_id, latencia_ms=latencia)

    def _fallo(self, texto, excepcion, trace_id, thread_id, inicio) -> RespuestaAgente:
        latencia = round((time.perf_counter() - inicio) * 1000)
        registrar(
            "turn_error",
            trace_id=trace_id,
            thread_id=thread_id,
            model=self.modelo,
            error=type(excepcion).__name__,
            latency_ms=latencia,
        )
        return RespuestaAgente(
            texto=texto, trace_id=trace_id, latencia_ms=latencia, error=type(excepcion).__name__
        )


def extraer_pasos(mensajes: list) -> list[PasoHerramienta]:
    """Empareja cada llamada del LLM con el resultado de la herramienta."""
    argumentos = {}
    pasos = []
    for mensaje in mensajes:
        if isinstance(mensaje, AIMessage):
            for llamada in mensaje.tool_calls or []:
                argumentos[llamada["id"]] = llamada.get("args", {})
        elif isinstance(mensaje, ToolMessage):
            resultado = mensaje.artifact if isinstance(mensaje.artifact, dict) else None
            if resultado is None:
                try:
                    resultado = json.loads(mensaje.content)
                except (json.JSONDecodeError, TypeError):
                    resultado = {"status": "ERROR", "message": str(mensaje.content)}
            pasos.append(
                PasoHerramienta(
                    nombre=mensaje.name or "desconocida",
                    argumentos=argumentos.get(mensaje.tool_call_id, {}),
                    resultado=resultado,
                )
            )
    return pasos


def texto_final(mensajes: list) -> str:
    """Último mensaje del agente con texto (no una llamada a herramienta)."""
    for mensaje in reversed(mensajes):
        if isinstance(mensaje, AIMessage) and not mensaje.tool_calls:
            contenido = mensaje.content
            if isinstance(contenido, list):
                contenido = "".join(
                    b.get("text", "") if isinstance(b, dict) else str(b) for b in contenido
                )
            if contenido and contenido.strip():
                return contenido.strip()
    return ""
