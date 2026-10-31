"""Registro de auditoría del agente.

Cada acción queda en `logs/auditoria.jsonl` (una línea JSON por evento) con un
`trace_id` por turno y el `thread_id` de la conversación:

    turn_start / turn_end   mensaje recibido, latencia total, herramientas usadas
    llm_end                 modelo, tokens de entrada y salida, latencia
    tool_start / tool_end   herramienta, argumentos, status, error_code, latencia
    tool_error / turn_error excepciones

Los datos personales se enmascaran antes de escribir (correos, teléfonos,
números largos) y de las salidas de las herramientas solo se guardan los
campos de control (status, error_code, eligible, rma, ticket), nunca el
nombre del cliente.
"""

import json
import os
import re
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

RAIZ = Path(__file__).resolve().parents[2]

CAMPOS_DE_CONTROL = (
    "status",
    "error_code",
    "eligible",
    "return_method",
    "rejection_reason",
    "rma",
    "already_existed",
    "ticket_id",
)

_PATRONES_PII = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<correo>"),
    (re.compile(r"\+?\d[\d\s-]{8,}\d"), "<numero>"),
)

_candado = threading.Lock()

# trace_id y thread_id del turno en curso, para eventos registrados fuera del callback
# (por ejemplo, la guarda de salida).
_contexto: ContextVar[dict] = ContextVar("contexto_auditoria", default={})


def fijar_contexto(**datos) -> None:
    _contexto.set(datos)


def ruta_auditoria() -> Path:
    return Path(os.getenv("AUDITORIA_RUTA", RAIZ / "logs" / "auditoria.jsonl"))


def enmascarar(valor: Any) -> Any:
    """Enmascara PII en textos y, recursivamente, en diccionarios y listas."""
    if isinstance(valor, str):
        for patron, reemplazo in _PATRONES_PII:
            valor = patron.sub(reemplazo, valor)
        return valor[:500]
    if isinstance(valor, dict):
        return {clave: enmascarar(v) for clave, v in valor.items()}
    if isinstance(valor, list):
        return [enmascarar(v) for v in valor]
    return valor


def registrar(evento: str, **datos) -> None:
    """Escribe un evento en el registro de auditoría."""
    linea = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "event": evento,
        **_contexto.get(),
        **datos,
    }
    ruta = ruta_auditoria()
    with _candado:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def leer_eventos(thread_id: str | None = None, limite: int = 500) -> list[dict]:
    """Últimos eventos del registro, opcionalmente de una sola conversación."""
    ruta = ruta_auditoria()
    if not ruta.exists():
        return []
    eventos = [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea]
    if thread_id:
        eventos = [e for e in eventos if e.get("thread_id") == thread_id]
    return eventos[-limite:]


def _campos_de_control(salida: Any) -> dict:
    """Extrae status, error_code, etc. de la salida de una herramienta."""
    datos = getattr(salida, "artifact", None)
    if not isinstance(datos, dict):
        contenido = getattr(salida, "content", salida)
        try:
            datos = json.loads(contenido) if isinstance(contenido, str) else {}
        except json.JSONDecodeError:
            datos = {}
    return {clave: datos[clave] for clave in CAMPOS_DE_CONTROL if clave in datos}


class Auditoria(BaseCallbackHandler):
    """Callback de LangChain que registra cada llamada al LLM y a las herramientas."""

    def __init__(self, thread_id: str, trace_id: str, modelo: str):
        self.thread_id = thread_id
        self.trace_id = trace_id
        self.modelo = modelo
        self._inicio: dict[UUID, float] = {}
        self._herramienta: dict[UUID, str] = {}
        self.herramientas_usadas: list[str] = []
        self.tokens = {"input": 0, "output": 0}

    def _registrar(self, evento: str, **datos) -> None:
        registrar(evento, trace_id=self.trace_id, thread_id=self.thread_id, **datos)

    def _latencia(self, run_id: UUID) -> int | None:
        inicio = self._inicio.pop(run_id, None)
        return round((time.perf_counter() - inicio) * 1000) if inicio else None

    # LLM -----------------------------------------------------------------

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, **kwargs) -> None:
        self._inicio[run_id] = time.perf_counter()

    def on_llm_end(self, response, *, run_id: UUID, **kwargs) -> None:
        uso, llamadas = {}, []
        try:
            mensaje = response.generations[0][0].message
            uso = getattr(mensaje, "usage_metadata", None) or {}
            llamadas = [c["name"] for c in getattr(mensaje, "tool_calls", []) or []]
        except (IndexError, AttributeError):
            pass
        self.tokens["input"] += uso.get("input_tokens", 0)
        self.tokens["output"] += uso.get("output_tokens", 0)
        self._registrar(
            "llm_end",
            model=self.modelo,
            input_tokens=uso.get("input_tokens"),
            output_tokens=uso.get("output_tokens"),
            tool_calls=llamadas,
            latency_ms=self._latencia(run_id),
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs) -> None:
        self._registrar(
            "llm_error", model=self.modelo, error=type(error).__name__, latency_ms=self._latencia(run_id)
        )

    # Herramientas ----------------------------------------------------------

    def on_tool_start(self, serialized, input_str, *, run_id: UUID, inputs=None, **kwargs) -> None:
        nombre = (serialized or {}).get("name") or kwargs.get("name") or "desconocida"
        self._inicio[run_id] = time.perf_counter()
        self._herramienta[run_id] = nombre
        self.herramientas_usadas.append(nombre)
        argumentos = inputs if isinstance(inputs, dict) else input_str
        if isinstance(argumentos, dict):
            argumentos = {k: v for k, v in argumentos.items() if k != "runtime"}
        self._registrar("tool_start", tool=nombre, arguments=enmascarar(argumentos))

    def on_tool_end(self, output, *, run_id: UUID, **kwargs) -> None:
        self._registrar(
            "tool_end",
            tool=self._herramienta.pop(run_id, None),
            latency_ms=self._latencia(run_id),
            **_campos_de_control(output),
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs) -> None:
        self._registrar(
            "tool_error",
            tool=self._herramienta.pop(run_id, None),
            error=type(error).__name__,
            latency_ms=self._latencia(run_id),
        )
