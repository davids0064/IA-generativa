"""Guarda de salida: impide que el agente anuncie acciones que no ejecutó.

Las guardas de las herramientas (confirmación verificada, elegibilidad
recalculada, idempotencia) solo actúan cuando el LLM llama a la herramienta.
Las pruebas con `qwen2.5:7b` mostraron el fallo contrario: el modelo *narra*
la acción en lugar de ejecutarla ("Verificaremos si el producto es elegible",
"Escalaremos tu caso") o, peor, la da por hecha e inventa el identificador
("¡Listo! Tu RMA es RMA-7C7AECD233").

Este middleware revisa cada respuesta final del modelo (`after_model`) y actúa
en cuatro situaciones, en este orden:

1. **Confirmación sin etiqueta.** El cliente acaba de confirmar una devolución
   cuya elegibilidad ya se verificó y el modelo no generó la etiqueta. Todo lo
   necesario para la acción es conocido y determinista, así que la guarda
   sintetiza la llamada a `generar_etiqueta_devolucion` y salta al nodo de
   herramientas; el LLM solo redacta el resultado.
2. **Identificador inventado.** El texto menciona un RMA-… o TCK-… que
   ninguna herramienta devolvió. Se borra el identificador del mensaje y se
   devuelve el control al modelo con una nota de corrección.
3. **Escalamiento sin ticket.** El texto dice que el caso se escala o se
   escaló ("Escalamos el caso a un asesor") y `escalar_a_humano` no se
   ejecutó con éxito en la conversación. Se revisa aunque el turno haya usado
   otras herramientas: en la evaluación, el modelo prometió el escalamiento
   justo después de que la transportadora fallara al generar la etiqueta.
4. **Acción anunciada sin ejecutar.** El texto anuncia que el agente va a
   verificar, consultar, generar o escalar, pero en el turno no se llamó a
   ninguna herramienta. Se devuelve el control al modelo con una nota.

En los casos 2 a 4 la respuesta original se conserva en el historial: en las
pruebas, el modelo corrige su conducta cuando ve lo que dijo junto a la nota,
y no lo hace si la respuesta se elimina. Si tras una corrección el modelo
vuelve a fallar con un identificador inventado o un escalamiento sin ticket,
la respuesta se reemplaza por un mensaje seguro; una acción solo anunciada se
entrega tal cual. Si tras la nota el modelo responde vacío, también se usa el
mensaje seguro: de lo contrario el cliente vería la respuesta falsa conservada.
"""

import re
import uuid
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage

from src.agente.herramientas import confirmacion_en_conversacion
from src.agente.observabilidad import registrar

PATRON_IDENTIFICADOR = re.compile(r"\b(?:RMA|TCK)-[A-Z0-9-]+\b", re.IGNORECASE)
# Anuncios de una acción futura, en curso o dada por hecha ("verificaremos", "voy a
# revisar", "escalamos tu caso", "te transfiero"). El subjuntivo de una pregunta
# ("¿quieres que verifiquemos?") no coincide.
PATRON_ACCION_ANUNCIADA = re.compile(
    r"\b(?:verificar[eé](?:mos)?|revisar[eé](?:mos)?|consultar[eé](?:mos)?|"
    r"generar[eé](?:mos)?|escalar[eé](?:mos)?|crear[eé](?:mos)?|transferir[eé](?:mos)?|"
    r"verificamos|revisamos|consultamos|generamos|escalamos|creamos|transferimos|"
    r"(?:vamos|voy) a (?:verificar|revisar|consultar|generar|escalar|crear|transferir)|"
    r"(?:estoy|estamos) (?:verificando|revisando|consultando|generando|escalando)|"
    r"(?:ahora|ya|enseguida|en seguida),? (?:verifico|reviso|consulto|genero|escalo|transfiero)|"
    r"te (?:transfiero|comunico con))\b",
    re.IGNORECASE,
)
# Afirmaciones de que el caso se escala o ya se escaló. Solo son ciertas si
# escalar_a_humano creó el ticket. Los ofrecimientos se descartan en
# `afirma_escalamiento`; el subjuntivo ("¿quieres que lo escale?") no coincide.
PATRON_ESCALAMIENTO = re.compile(
    r"\b(?:escalar[eé](?:mos)?|escalamos|escalé|"
    r"(?:vamos|voy) a (?:escalar|transferir)|(?:estoy|estamos) (?:escalando|transfiriendo)|"
    r"(?:he|hemos|ha|han) (?:escalado|transferido)|"
    r"(?:fue|ha sido|será|queda|quedó) (?:escalado|transferido)|"
    r"transferimos|transferiremos)\b",
    re.IGNORECASE,
)
MARCA_CORRECCION = "[CORRECCIÓN AUTOMÁTICA]"
IDENTIFICADOR_NO_VALIDO = "[identificador no válido]"
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
NOTA_ESCALAMIENTO = (
    "Le dijiste al cliente que su caso se escala a un asesor, pero no se ha creado ningún "
    "ticket. Llama ahora a escalar_a_humano con el motivo y un resumen del caso, o no "
    "afirmes que el caso fue escalado."
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


def afirma_escalamiento(texto: str) -> bool:
    """Si alguna oración afirma el escalamiento; las preguntas y los condicionales
    ("Si lo deseas, escalamos tu caso") son ofrecimientos, no afirmaciones."""
    for oracion in re.split(r"(?<=[.!?\n])", texto):
        oracion = oracion.strip()
        if not PATRON_ESCALAMIENTO.search(oracion):
            continue
        if "¿" in oracion or oracion.endswith("?") or oracion.lower().startswith("si "):
            continue
        return True
    return False


def caso_escalado(mensajes: list) -> bool:
    """Si escalar_a_humano creó un ticket en algún punto de la conversación."""
    return any(
        isinstance(m, ToolMessage)
        and m.name == "escalar_a_humano"
        and isinstance(m.artifact, dict)
        and m.artifact.get("status") == "SUCCESS"
        for m in mensajes
    )


def _respuesta_falsa(texto: str, mensajes: list) -> bool:
    """Respuesta corregida por afirmar algo que no ocurrió (identificador o escalamiento)."""
    return IDENTIFICADOR_NO_VALIDO in texto or (afirma_escalamiento(texto) and not caso_escalado(mensajes))


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

        # Respuesta vacía tras una corrección: el texto que vería el cliente sería la
        # respuesta falsa que se conservó en el historial para que el modelo la corrigiera.
        if not texto.strip():
            anteriores = [m for m in turno if isinstance(m, AIMessage) and not m.tool_calls]
            if any(_respuesta_falsa(_contenido(m), mensajes) for m in anteriores):
                registrar("guard_triggered", reason="respuesta_vacia_tras_correccion")
                return {"messages": [AIMessage(content=MENSAJE_SEGURO, id=ultimo.id)]}
            return None

        # 2 a 4. Identificador inventado, escalamiento sin ticket o acción anunciada
        # sin herramientas en el turno.
        inventados = identificadores_inventados(texto, mensajes[:-1])
        sin_herramientas = not any(isinstance(m, ToolMessage) for m in turno)
        escalamiento_falso = afirma_escalamiento(texto) and not caso_escalado(mensajes)
        if inventados:
            motivo_guarda, nota = "identificador_inventado", NOTA_IDENTIFICADOR
        elif escalamiento_falso:
            motivo_guarda, nota = "escalamiento_sin_ticket", NOTA_ESCALAMIENTO
        elif sin_herramientas and PATRON_ACCION_ANUNCIADA.search(texto):
            motivo_guarda, nota = "accion_anunciada_sin_ejecutar", NOTA_ACCION_ANUNCIADA
        else:
            return None

        correcciones = sum(
            1 for m in turno if isinstance(m, SystemMessage) and _contenido(m).startswith(MARCA_CORRECCION)
        )
        registrar("guard_triggered", reason=motivo_guarda, corrections=correcciones)
        if correcciones >= MAX_CORRECCIONES:
            if inventados or escalamiento_falso:
                # Mismo id: el reductor de mensajes reemplaza la respuesta falsa.
                return {"messages": [AIMessage(content=MENSAJE_SEGURO, id=ultimo.id)]}
            return None  # una acción anunciada no es falsa: se entrega tras un intento de corrección

        conservado = ultimo
        if inventados:
            # La respuesta queda en el historial sin el identificador falso, para no reutilizarlo.
            conservado = AIMessage(
                content=PATRON_IDENTIFICADOR.sub(IDENTIFICADOR_NO_VALIDO, texto), id=ultimo.id
            )
        return {
            "messages": [conservado, SystemMessage(f"{MARCA_CORRECCION} {nota}")],
            "jump_to": "model",
        }
