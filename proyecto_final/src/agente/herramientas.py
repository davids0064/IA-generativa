"""Herramientas del agente de devoluciones (diseño de la Fase 1).

Cinco herramientas, todas con la misma convención de salida:

- Entradas validadas con un esquema Pydantic.
- Nunca lanzan excepciones al agente: devuelven siempre un objeto con
  `status` = "SUCCESS" o "ERROR". En error incluyen `error_code`, `message` y,
  cuando aplica, `suggested_action`.
- Atributos del JSON en inglés; valores en español.
- Se declaran con `response_format="content_and_artifact"`: el LLM recibe el
  JSON como texto y la interfaz recibe el mismo diccionario como artefacto
  (por ejemplo, para ofrecer la descarga de la etiqueta).

Las lógicas de negocio viven en funciones normales (`verificar_elegibilidad`,
`generar_etiqueta`, ...) para poder probarlas sin LLM; los objetos `@tool` solo
las envuelven.
"""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from typing import Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from src import base_conocimiento, db, rag
from src.agente import reglas, simulador

log = logging.getLogger(__name__)

PATRON_TRACKING = re.compile(r"^ECO-\d{4}-\d{4}$")

Motivo = Literal[
    "cambio_de_opinion",
    "talla_incorrecta",
    "producto_danado",
    "producto_defectuoso",
    "producto_equivocado",
    "otro",
]
MotivoEscalamiento = Literal[
    "solicitud_cliente",
    "molestia",
    "incidencia",
    "devolucion_en_curso",
    "motivo_otro",
    "error_sistema",
    "fuera_de_alcance",
]

# Respuestas que cuentan como confirmación explícita del cliente.
PATRON_AFIRMACION = re.compile(
    r"\b(s[ií]|confirm[oa]|confirmado|dale|de acuerdo|ok|okay|claro|adelante|hazlo|"
    r"gen[eé]ral[ao]|procede|proceder|perfecto|listo|correcto|est[aá] bien|por supuesto)\b",
    re.IGNORECASE,
)
PATRON_NEGACION = re.compile(
    r"^\W*no\b|\b(no quiero|no gracias|mejor no|todav[ií]a no|a[uú]n no|cancela)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------


def exito(**datos) -> dict:
    return {"status": "SUCCESS", **datos}


def error(codigo: str, mensaje: str, accion: str | None = None, **extra) -> dict:
    respuesta = {"status": "ERROR", "error_code": codigo, "message": mensaje}
    if accion:
        respuesta["suggested_action"] = accion
    return {**respuesta, **extra}


def _salida(datos: dict) -> tuple[str, dict]:
    """Contenido para el LLM (JSON) + artefacto para la interfaz (dict)."""
    return json.dumps(datos, ensure_ascii=False), datos


def _proteger(funcion: Callable[[], dict]) -> dict:
    """Convierte cualquier excepción inesperada en un ERROR estructurado."""
    try:
        return funcion()
    except Exception:  # noqa: BLE001 — la herramienta nunca debe romper el agente
        log.exception("Error inesperado en una herramienta")
        return error(
            "ERROR_INTERNO",
            "Ocurrió un error inesperado al procesar la solicitud.",
            "Discúlpate con el cliente y ofrece escalar el caso a un asesor con escalar_a_humano.",
        )


def _error_argumentos(excepcion: Exception) -> str:
    """Respuesta cuando el LLM envía argumentos que no cumplen el esquema."""
    return json.dumps(
        error(
            "ARGUMENTOS_INVALIDOS",
            f"Los argumentos no cumplen el formato esperado: {type(excepcion).__name__}.",
            "Revisa los valores permitidos de cada argumento y vuelve a intentarlo; "
            "si falta información, pídela al cliente.",
        ),
        ensure_ascii=False,
    )


def normalizar_tracking(tracking_number: str) -> str:
    return (tracking_number or "").strip().upper()


def _validar_pedido(tracking_number: str) -> tuple[dict | None, dict | None]:
    """Devuelve (pedido, None) o (None, error) según el formato y la existencia."""
    tracking = normalizar_tracking(tracking_number)
    if not PATRON_TRACKING.match(tracking):
        return None, error(
            "FORMATO_TRACKING_INVALIDO",
            f"'{tracking_number}' no tiene el formato de un número de seguimiento.",
            "Pide al cliente el número de seguimiento con el formato ECO-AAAA-NNNN "
            "(por ejemplo ECO-2024-0001).",
        )
    pedido = db.buscar_pedido(tracking)
    if pedido is None:
        return None, error(
            "PEDIDO_NO_ENCONTRADO",
            f"No existe un pedido con el número {tracking}.",
            "Pide al cliente que verifique el número; si vuelve a fallar, ofrece un asesor.",
        )
    return pedido, None


def _token_elegibilidad(tracking: str, motivo: str, fecha: str) -> str:
    """Huella de la verificación; queda registrada en la RMA para auditoría."""
    huella = hashlib.sha256(f"{tracking}|{motivo}|{fecha}".encode()).hexdigest()[:10]
    return f"ELG-{huella.upper()}"


# ---------------------------------------------------------------------------
# Lógica de cada herramienta (sin LLM, probada con pytest)
# ---------------------------------------------------------------------------


def consultar_base(consulta: str, sku: str | None = None) -> dict:
    if not consulta or not consulta.strip():
        return error("ARGUMENTOS_INVALIDOS", "La consulta está vacía.", "Pide al cliente su pregunta.")
    try:
        documentos = rag.recuperar(consulta, sku=sku or None)
    except Exception:  # noqa: BLE001 — ChromaDB caído, colección inexistente o embeddings sin servicio
        log.exception("Base de conocimiento no disponible")
        return error(
            "BASE_CONOCIMIENTO_NO_DISPONIBLE",
            "La base de conocimiento no está disponible en este momento.",
            "Informa al cliente que no puedes consultar la política ahora; las devoluciones "
            "se pueden verificar igual con verificar_elegibilidad_producto.",
        )
    if not documentos:
        return error(
            "SIN_RESULTADOS",
            "No se encontraron fragmentos relacionados con la consulta.",
            "Responde que no tienes esa información y ofrece un asesor.",
        )
    return exito(
        fragments=rag.formatear_contexto(documentos),
        sources=[rag._etiqueta(doc) for doc in documentos],
    )


def consultar(tracking_number: str) -> dict:
    pedido, problema = _validar_pedido(tracking_number)
    if problema:
        return problema
    orden = {
        "tracking_number": pedido["tracking_number"],
        "customer": pedido["customer"].split()[0],
        "product": pedido["product"],
        "category": pedido["product_category"],
        "order_status": pedido["status"],
        "order_date": pedido["order_date"],
        "estimated_delivery_date": pedido["estimated_delivery_date"],
        "delivered_date": pedido["delivered_date"],
        "carrier": pedido["carrier"],
        "notes": pedido["notes"],
    }
    # Para pedidos entregados la ubicación es la dirección del cliente: no se expone.
    if pedido["status"] != "Entregado":
        orden["current_location"] = pedido["current_location"]
    return exito(order=orden)


def verificar_elegibilidad(tracking_number: str, motivo: str) -> dict:
    pedido, problema = _validar_pedido(tracking_number)
    if problema:
        return problema
    if motivo not in reglas.MOTIVOS:
        return error(
            "MOTIVO_INVALIDO",
            f"'{motivo}' no es un motivo de devolución válido.",
            f"Pregunta al cliente el motivo y usa uno de: {', '.join(reglas.MOTIVOS)}.",
        )

    hoy = reglas.fecha_referencia()
    resultado = reglas.evaluar_elegibilidad(pedido, motivo, hoy)
    datos = {
        "tracking_number": pedido["tracking_number"],
        "customer": pedido["customer"].split()[0],
        "product": pedido["product"],
        "order_status": pedido["status"],
        "reason": motivo,
        "eligible": resultado.eligible,
        "policy_reference": resultado.policy_reference,
        "escalate_to_human": resultado.escalate_to_human,
    }
    if resultado.business_days is not None:
        datos["days_since_delivery"] = {
            "business_days": resultado.business_days,
            "calendar_days": resultado.calendar_days,
        }
    if resultado.eligible:
        datos.update(
            return_method=resultado.return_method,
            requires_physical_return=resultado.requires_physical_return,
            return_window=resultado.return_window,
            return_process=resultado.return_process,
            refund_timeframe=resultado.refund_timeframe,
            eligibility_token=_token_elegibilidad(
                pedido["tracking_number"], motivo, hoy.isoformat()
            ),
        )
    else:
        datos.update(
            rejection_reason=resultado.rejection_reason,
            alternative=resultado.alternative,
        )
    return exito(**datos)


def confirmacion_en_conversacion(mensajes: list, tracking: str) -> bool:
    """Verifica en el historial que el cliente confirmó de verdad la devolución.

    Exige que (1) en un turno anterior se haya verificado la elegibilidad de ese
    pedido con resultado positivo y (2) el último mensaje del cliente sea una
    afirmación. Así el LLM no puede marcar `confirmado_por_cliente=true` por su
    cuenta en el mismo turno en que el cliente pidió la devolución.
    """
    indices_humanos = [i for i, m in enumerate(mensajes) if isinstance(m, HumanMessage)]
    if not indices_humanos:
        return False
    ultimo = indices_humanos[-1]
    texto = str(mensajes[ultimo].content)
    if not PATRON_AFIRMACION.search(texto) or PATRON_NEGACION.search(texto):
        return False

    for mensaje in mensajes[:ultimo]:
        if (
            isinstance(mensaje, ToolMessage)
            and mensaje.name == "verificar_elegibilidad_producto"
            and isinstance(mensaje.artifact, dict)
            and mensaje.artifact.get("eligible") is True
            and mensaje.artifact.get("tracking_number") == tracking
        ):
            # Además, el agente debió hacer la pregunta antes de la respuesta del cliente.
            return any(isinstance(m, AIMessage) and m.content for m in mensajes[:ultimo])
    return False


def generar_etiqueta(
    tracking_number: str,
    motivo: str,
    confirmado_por_cliente: bool,
    mensajes: list | None = None,
) -> dict:
    """Crea la RMA. `mensajes` es el historial del agente; `None` omite la
    verificación conversacional (uso directo en pruebas unitarias)."""
    pedido, problema = _validar_pedido(tracking_number)
    if problema:
        return problema
    tracking = pedido["tracking_number"]

    # Idempotencia: una sola devolución activa por pedido.
    existente = simulador.buscar_rma(tracking)
    if existente:
        return exito(**_resumen_rma(existente), already_existed=True)

    confirmado = confirmado_por_cliente and (
        mensajes is None or confirmacion_en_conversacion(mensajes, tracking)
    )
    if not confirmado:
        return error(
            "CONFIRMACION_REQUERIDA",
            "El cliente todavía no ha confirmado de forma explícita que quiere generar la "
            "devolución.",
            "Verifica la elegibilidad si no lo has hecho, resume al cliente cómo será la "
            "devolución y pregúntale si confirma. Genera la etiqueta solo cuando responda "
            "que sí.",
            tracking_number=tracking,
        )

    # No se confía en lo que el LLM haya concluido: la elegibilidad se recalcula.
    verificacion = verificar_elegibilidad(tracking, motivo)
    if verificacion["status"] == "ERROR":
        return {**verificacion, "tracking_number": tracking}
    if not verificacion["eligible"]:
        return error(
            "NO_ELEGIBLE",
            "El pedido no cumple las condiciones para generar una devolución.",
            "Explica el motivo al cliente en lenguaje sencillo y ofrécele la alternativa.",
            tracking_number=tracking,
            rejection_reason=verificacion["rejection_reason"],
            alternative=verificacion["alternative"],
        )

    try:
        rma = simulador.crear_rma(
            pedido,
            motivo,
            verificacion,
            verificacion["eligibility_token"],
            reglas.fecha_referencia(),
        )
    except simulador.ServicioNoDisponible:
        return error(
            "SERVICIO_TRANSPORTADORA_NO_DISPONIBLE",
            "La transportadora no respondió y no fue posible programar la recolección. "
            "La devolución sí es elegible.",
            "Discúlpate, informa que la devolución es elegible y escala el caso con "
            "escalar_a_humano (motivo error_sistema) para que un asesor la complete.",
            tracking_number=tracking,
            eligible=True,
        )
    return exito(**_resumen_rma(rma), already_existed=False)


def _resumen_rma(rma: dict) -> dict:
    return {
        "rma": rma["rma"],
        "tracking_number": rma["tracking_number"],
        "return_method": rma["return_method"],
        "return_type": rma["return_type"],
        "carrier": rma["carrier"],
        "waybill_number": rma["waybill_number"],
        "pickup_window": rma["pickup_window"],
        "label_file": rma["label_file"],
        "instructions": rma["instructions"],
        "refund_timeframe": rma["refund_timeframe"],
    }


def escalar(motivo: str, resumen: str, tracking_number: str | None = None) -> dict:
    tracking = normalizar_tracking(tracking_number) if tracking_number else None
    if tracking and not PATRON_TRACKING.match(tracking):
        tracking = None
    ticket = simulador.crear_ticket(
        motivo, (resumen or "").strip()[:500], tracking, reglas.fecha_referencia()
    )
    return exito(
        ticket_id=ticket["ticket_id"],
        response_time=ticket["response_time"],
        business_hours=ticket["business_hours"],
    )


# ---------------------------------------------------------------------------
# Esquemas de entrada
# ---------------------------------------------------------------------------

DESCRIPCION_TRACKING = "Número de seguimiento del pedido, formato ECO-AAAA-NNNN (ej. ECO-2024-0001)."
DESCRIPCION_MOTIVO = (
    "Motivo de la devolución según lo que dijo el cliente: cambio_de_opinion (se arrepintió, "
    "no le gustó), talla_incorrecta, producto_danado (llegó roto o dañado), "
    "producto_defectuoso (no funciona, dejó de funcionar), producto_equivocado (llegó otro "
    "producto) u otro."
)


class EntradaConsultaBase(BaseModel):
    consulta: str = Field(description="Pregunta del cliente sobre políticas, productos o FAQ.")
    sku: str | None = Field(
        default=None, description="SKU del producto, solo si ya se conoce. Opcional."
    )


class EntradaPedido(BaseModel):
    tracking_number: str = Field(description=DESCRIPCION_TRACKING)


class EntradaElegibilidad(BaseModel):
    tracking_number: str = Field(description=DESCRIPCION_TRACKING)
    motivo: Motivo = Field(description=DESCRIPCION_MOTIVO)


class EntradaEtiqueta(BaseModel):
    tracking_number: str = Field(description=DESCRIPCION_TRACKING)
    motivo: Motivo = Field(description=DESCRIPCION_MOTIVO)
    confirmado_por_cliente: bool = Field(
        description="true solo si el cliente respondió explícitamente que sí quiere generar "
        "la devolución después de que se la propusiste."
    )


class EntradaEscalamiento(BaseModel):
    motivo: MotivoEscalamiento = Field(description="Razón del escalamiento.")
    resumen: str = Field(description="Resumen breve del caso para el asesor.")
    tracking_number: str | None = Field(default=None, description="Número de seguimiento, si se conoce.")


# ---------------------------------------------------------------------------
# Herramientas expuestas al agente
# ---------------------------------------------------------------------------


@tool(args_schema=EntradaConsultaBase, response_format="content_and_artifact")
def consultar_base_conocimiento(consulta: str, sku: str | None = None) -> tuple[str, dict]:
    """Busca en el manual de políticas, el catálogo y las preguntas frecuentes de EcoMarket.

    Úsala para preguntas generales: plazos y condiciones de devolución, garantías,
    reembolsos, envíos, cancelaciones o características de un producto.
    No la uses para saber si un pedido concreto se puede devolver: para eso usa
    verificar_elegibilidad_producto.
    """
    return _salida(_proteger(lambda: consultar_base(consulta, sku)))


@tool(args_schema=EntradaPedido, response_format="content_and_artifact")
def consultar_pedido(tracking_number: str) -> tuple[str, dict]:
    """Consulta el estado, el producto y las fechas de un pedido.

    Úsala cuando el cliente pregunte dónde está su pedido o cuál es su estado.
    No decide devoluciones: para eso usa verificar_elegibilidad_producto.
    """
    return _salida(_proteger(lambda: consultar(tracking_number)))


@tool(args_schema=EntradaElegibilidad, response_format="content_and_artifact")
def verificar_elegibilidad_producto(tracking_number: str, motivo: str) -> tuple[str, dict]:
    """Decide si el producto de un pedido se puede devolver, por qué vía y con qué condiciones.

    Úsala siempre que el cliente quiera devolver un producto, una vez conozcas el
    número de seguimiento y el motivo. Si falta alguno de los dos, pregúntalo antes.
    Su resultado es la decisión oficial: no la contradigas. Si eligible es false,
    explica rejection_reason con palabras sencillas y ofrece la alternative.
    """
    return _salida(_proteger(lambda: verificar_elegibilidad(tracking_number, motivo)))


@tool(args_schema=EntradaEtiqueta, response_format="content_and_artifact")
def generar_etiqueta_devolucion(
    tracking_number: str, motivo: str, confirmado_por_cliente: bool, runtime: ToolRuntime
) -> tuple[str, dict]:
    """Crea la orden de devolución (RMA) y la etiqueta de envío o las instrucciones.

    Úsala solo después de que verificar_elegibilidad_producto devolvió eligible=true
    y el cliente confirmó explícitamente en su último mensaje que quiere la
    devolución. Nunca la uses si el pedido no es elegible.
    """
    mensajes = (runtime.state or {}).get("messages", []) if runtime else []
    return _salida(
        _proteger(lambda: generar_etiqueta(tracking_number, motivo, confirmado_por_cliente, mensajes))
    )


@tool(args_schema=EntradaEscalamiento, response_format="content_and_artifact")
def escalar_a_humano(
    motivo: str, resumen: str, tracking_number: str | None = None
) -> tuple[str, dict]:
    """Transfiere el caso a un asesor humano y crea un ticket.

    Úsala cuando el cliente pida hablar con una persona o esté molesto, cuando el
    motivo de devolución sea "otro", cuando una herramienta indique
    escalate_to_human=true, o cuando un error persista tras un reintento.
    """
    return _salida(_proteger(lambda: escalar(motivo, resumen, tracking_number)))


HERRAMIENTAS = [
    consultar_base_conocimiento,
    consultar_pedido,
    verificar_elegibilidad_producto,
    generar_etiqueta_devolucion,
    escalar_a_humano,
]
NOMBRES_HERRAMIENTAS = tuple(h.name for h in HERRAMIENTAS)

for _herramienta in HERRAMIENTAS:
    _herramienta.handle_validation_error = _error_argumentos
