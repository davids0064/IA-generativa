"""Guarda de salida: impide que el agente anuncie acciones que no ejecutó.

Las guardas de las herramientas (confirmación verificada, elegibilidad
recalculada, idempotencia) solo actúan cuando el LLM llama a la herramienta.
Las pruebas con `qwen2.5:7b` mostraron el fallo contrario: el modelo *narra*
la acción en lugar de ejecutarla ("Verificaremos si el producto es elegible",
"Escalaremos tu caso") o, peor, la da por hecha e inventa el identificador
("¡Listo! Tu RMA es RMA-7C7AECD233").

Este middleware revisa cada respuesta final del modelo (`after_model`) y actúa
en tres situaciones, en este orden:

1. **Confirmación sin etiqueta.** El cliente acaba de confirmar una devolución
   cuya elegibilidad ya se verificó y el modelo no generó la etiqueta. Todo lo
   necesario para la acción es conocido y determinista, así que la guarda
   sintetiza la llamada a `generar_etiqueta_devolucion` y salta al nodo de
   herramientas; el LLM solo redacta el resultado.
2. **Identificador inventado.** El texto menciona un RMA-… o TCK-… que
   ninguna herramienta devolvió. Se borra el identificador del mensaje y se
   devuelve el control al modelo con una nota de corrección.
3. **Acción anunciada sin ejecutar.** El texto anuncia que el agente va a
   verificar, consultar, generar o escalar, pero en el turno no se llamó a
   ninguna herramienta. Se devuelve el control al modelo con una nota.

En los casos 2 y 3 la respuesta original se conserva en el historial: en las
pruebas, el modelo corrige su conducta cuando ve lo que dijo junto a la nota,
y no lo hace si la respuesta se elimina. Si tras una corrección el modelo
vuelve a fallar, la respuesta se reemplaza por un mensaje seguro.
"""

import re
import uuid
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage

from src.agente.herramientas import confirmacion_en_conversacion
from src.agente.observabilidad import registrar

PATRON_IDENTIFICADOR = re.compile(r"\b(?:RMA|TCK)-[A-Z0-9-]+\b", re.IGNORECASE)
# Anuncios de una acción futura o en curso ("verificaremos", "voy a revisar", "te transfiero").
PATRON_ACCION_ANUNCIADA = re.compile(
    r"\b(?:verificar[eé](?:mos)?|revisar[eé](?:mos)?|consultar[eé](?:mos)?|"
    r"generar[eé](?:mos)?|escalar[eé](?:mos)?|crear[eé](?:mos)?|transferir[eé](?:mos)?|"
    r"(?:vamos|voy) a (?:verificar|revisar|consultar|generar|escalar|crear|transferir)|"
    r"(?:estoy|estamos) (?:verificando|revisando|consultando|generando|escalando)|"
    r"(?:ahora|ya|enseguida|en seguida),? (?:verifico|reviso|consulto|genero|escalo|transfiero)|"
    r"te (?:transfiero|comunico con))\b",
    re.IGNORECASE,
)
MARCA_CORRECCION = "[CORRECCIÓN AUTOMÁTICA]"
MAX_CORRECCIONES = 1

MENSAJE_SEGURO = (
    "Disculpa, no pude completar ese paso en este momento. ¿Quieres que lo intente de "
    "nuevo o prefieres que te comunique con un asesor?"
)
NOTA_IDENTIFICADOR = (
    "Tu respuesta mencionaba un número de RMA o de ticket que ninguna herramienta generó. "
    "No inventes identificadores: solo existen si una herramienta los devolvió."
)
NOTA_ACCION_ANUNCIADA = (
    "Anunciaste una acción pero no llamaste a ninguna herramienta. No describas lo que vas "
    "a hacer: si ya tienes los datos, llama ahora a la herramienta que corresponde "
    "(verificar_elegibilidad_producto, consultar_pedido, consultar_base_conocimiento o "
    "escalar_a_humano). Si te falta un dato, pídeselo al cliente sin anunciar acciones."
)


def _contenido(mensaje) -> str:
    contenido = mensaje.content
    if isinstance(contenido, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in contenido)
    return str(contenido or "")


def identificadores_inventados(texto: str, mensajes: list) -> list[str]:
    """Identificadores del texto que no aparecen en ninguna salida de herramienta."""
    salidas = " ".join(_contenido(m) for m in mensajes if isinstance(m, ToolMessage)).upper()
    return [i for i in PATRON_IDENTIFICADOR.findall(texto) if i.upper() not in salidas]


def devolucion_confirmada_sin_etiqueta(mensajes: list, indice_humano: int) -> tuple[str, str] | None:
    """(tracking, motivo) de la devolución que el cliente confirmó sin que se generara la etiqueta."""
    hasta_confirmacion = mensajes[: indice_humano + 1]
    verificados = {
        m.artifact["tracking_number"]: m.artifact.get("reason")
        for m in hasta_confirmacion
        if isinstance(m, ToolMessage)
        and m.name == "verificar_elegibilidad_producto"
        and isinstance(m.artifact, dict)
        and m.artifact.get("eligible") is True
    }
    con_etiqueta = {
        m.artifact.get("tracking_number")
        for m in mensajes
        if isinstance(m, ToolMessage)
        and m.name == "generar_etiqueta_devolucion"
        and isinstance(m.artifact, dict)
        # Un intento que falló por falta de confirmación no cuenta: tras confirmar hay que reintentar.
        and m.artifact.get("error_code") not in ("CONFIRMACION_REQUERIDA", "ARGUMENTOS_INVALIDOS")
    }
    intento_en_turno = any(
        isinstance(m, ToolMessage) and m.name == "generar_etiqueta_devolucion"
        for m in mensajes[indice_humano + 1 :]
    )
    if intento_en_turno:
        return None
    for tracking in sorted(set(verificados) - con_etiqueta):
        if verificados[tracking] and confirmacion_en_conversacion(hasta_confirmacion, tracking):
            return tracking, verificados[tracking]
    return None


class GuardiaAccionesInventadas(AgentMiddleware):
    """Corrige respuestas que anuncian acciones no ejecutadas (ver docstring del módulo)."""

    @hook_config(can_jump_to=["model", "tools"])
    def after_model(self, state: dict, runtime: Any) -> dict | None:
        mensajes = state["messages"]
        ultimo = mensajes[-1] if mensajes else None
        if not isinstance(ultimo, AIMessage) or ultimo.tool_calls:
            return None
        indices = [i for i, m in enumerate(mensajes) if isinstance(m, HumanMessage)]
        if not indices:
            return None
        indice_humano = indices[-1]
        turno = mensajes[indice_humano + 1 : -1]
        texto = _contenido(ultimo)

        # 1. Confirmación sin etiqueta: la acción se ejecuta de forma determinista.
        pendiente = devolucion_confirmada_sin_etiqueta(mensajes, indice_humano)
        if pendiente:
            tracking, motivo = pendiente
            registrar("guard_triggered", reason="confirmacion_sin_etiqueta", action="ejecucion_directa")
            llamada = {
                "name": "generar_etiqueta_devolucion",
                "args": {"tracking_number": tracking, "motivo": motivo, "confirmado_por_cliente": True},
                "id": f"guardia-{uuid.uuid4().hex[:8]}",
            }
            return {
                "messages": [RemoveMessage(id=ultimo.id), AIMessage(content="", tool_calls=[llamada])],
                "jump_to": "tools",
            }

        # 2 y 3. Identificador inventado o acción anunciada sin herramientas en el turno.
        inventados = identificadores_inventados(texto, mensajes[:-1])
        sin_herramientas = not any(isinstance(m, ToolMessage) for m in turno)
        if inventados:
            motivo_guarda, nota = "identificador_inventado", NOTA_IDENTIFICADOR
        elif sin_herramientas and PATRON_ACCION_ANUNCIADA.search(texto):
            motivo_guarda, nota = "accion_anunciada_sin_ejecutar", NOTA_ACCION_ANUNCIADA
        else:
            return None

        correcciones = sum(
            1 for m in turno if isinstance(m, SystemMessage) and _contenido(m).startswith(MARCA_CORRECCION)
        )
        registrar("guard_triggered", reason=motivo_guarda, corrections=correcciones)
        if correcciones >= MAX_CORRECCIONES:
            if inventados:
                # Mismo id: el reductor de mensajes reemplaza la respuesta inventada.
                return {"messages": [AIMessage(content=MENSAJE_SEGURO, id=ultimo.id)]}
            return None  # una acción anunciada no es falsa: se entrega tras un intento de corrección

        conservado = ultimo
        if inventados:
            # La respuesta queda en el historial sin el identificador falso, para no reutilizarlo.
            conservado = AIMessage(
                content=PATRON_IDENTIFICADOR.sub("[identificador no válido]", texto), id=ultimo.id
            )
        return {
            "messages": [conservado, SystemMessage(f"{MARCA_CORRECCION} {nota}")],
            "jump_to": "model",
        }
