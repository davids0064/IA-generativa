"""Reglas de devolución de EcoMarket como lógica pura, sin LLM.

En el Taller 2 el árbol de decisión vivía en el prompt
(`prompts_devolucion_rag.py`) y el modelo lo aplicaba sobre la política
recuperada. Con `qwen2.5:3b` eso falló cuando debían combinarse dos garantías
(caso 3 de las pruebas). Aquí el mismo árbol se ejecuta en Python: la decisión
es determinista, auditable y se prueba con pytest; el LLM solo decide cuándo
pedirla y cómo comunicarla.

Las reglas reproducen el manual de políticas (`data/conocimiento/
manual_politicas_garantias.md`), secciones 2 a 5 y 7.
"""

import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta

MOTIVOS = (
    "cambio_de_opinion",
    "talla_incorrecta",
    "producto_danado",
    "producto_defectuoso",
    "producto_equivocado",
    "otro",
)
MOTIVOS_RETRACTO = ("cambio_de_opinion", "talla_incorrecta")
MOTIVOS_GARANTIA = ("producto_danado", "producto_defectuoso", "producto_equivocado")

ESTADOS_EN_CAMINO = ("En tránsito", "En reparto", "Retrasado")
CATEGORIAS_EXCLUIDAS_RETRACTO = ("Alimentos", "Suscripción", "Higiene personal")

VENTANA_RETRACTO_DIAS_HABILES = 5
VENTANA_GARANTIA_DIAS = 30
# 12 meses de garantía del fabricante, contando 30 días calendario por mes
# (misma convención del prompt de devoluciones del Taller 2).
VENTANA_FABRICANTE_DIAS = 12 * 30

PLAZO_REEMBOLSO = "5 a 10 días hábiles"

# Cómo se ejecuta cada tipo de devolución, en palabras para el cliente.
PROCESO_RETRACTO = (
    "EcoMarket recoge el producto sin costo en la dirección del cliente; debe estar sin uso, "
    "con su empaque original y el sello intacto."
)
PROCESO_GARANTIA_RECOLECCION = "EcoMarket recoge el producto sin costo en la dirección del cliente."
PROCESO_GARANTIA_FOTO = (
    "No hay que devolver el producto: por bioseguridad basta con enviar una foto del producto y "
    "su empaque."
)
PROCESO_FABRICANTE = (
    "EcoMarket recoge el producto sin costo y gestiona con el fabricante la reparación o el "
    "reemplazo; no cubre daños por mal uso, humedad o golpes."
)


@dataclass(frozen=True)
class ResultadoElegibilidad:
    """Veredicto de una solicitud de devolución.

    Los nombres de los campos coinciden con los atributos del JSON que devuelve
    la herramienta `verificar_elegibilidad_producto`.
    """

    eligible: bool
    return_method: str | None = None
    requires_physical_return: bool | None = None
    rejection_reason: str | None = None
    alternative: str | None = None
    policy_reference: str = ""
    return_window: str | None = None
    return_process: str | None = None
    refund_timeframe: str | None = None
    business_days: int | None = None
    calendar_days: int | None = None
    escalate_to_human: bool = False

    def a_dict(self) -> dict:
        return asdict(self)


def fecha_referencia() -> date:
    """Fecha contra la que se calculan las ventanas.

    `FECHA_REFERENCIA` (YYYY-MM-DD) fija el "hoy" para que las pruebas y la
    demostración sean reproducibles con el dataset simulado; sin ella se usa la
    fecha real.
    """
    valor = os.getenv("FECHA_REFERENCIA")
    return date.fromisoformat(valor) if valor else date.today()


def dias_habiles(desde: date, hasta: date) -> int:
    """Cuenta los días hábiles transcurridos entre dos fechas, sin contar `desde`.

    Solo excluye sábados y domingos: los festivos colombianos quedan fuera del
    alcance del proyecto y en producción vendrían de un calendario oficial.
    """
    dias = 0
    cursor = desde + timedelta(days=1)
    while cursor <= hasta:
        if cursor.weekday() < 5:
            dias += 1
        cursor += timedelta(days=1)
    return dias


def _excluido_de_retracto(pedido: dict) -> bool:
    return (
        pedido.get("is_perishable", False)
        or pedido.get("is_hygiene_item", False)
        or pedido.get("product_category") in CATEGORIAS_EXCLUIDAS_RETRACTO
    )


def _sin_devolucion_fisica(pedido: dict) -> bool:
    """Perecederos e higiene se resuelven en garantía sin recoger el producto (§4.2)."""
    return pedido.get("is_perishable", False) or pedido.get("is_hygiene_item", False)


def _evaluar_no_entregado(estado: str) -> ResultadoElegibilidad:
    """Guion por estado cuando el pedido todavía no permite una devolución."""
    if estado == "Procesando":
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="pedido_no_entregado",
            alternative="El pedido aún no sale de bodega: se puede cancelar sin costo "
            "y el reembolso es del 100 %.",
            policy_reference="Manual §3",
        )
    if estado in ESTADOS_EN_CAMINO:
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="pedido_no_entregado",
            alternative="El pedido ya fue despachado: se puede rechazar el paquete al "
            "momento de la entrega o iniciar la devolución cuando llegue.",
            policy_reference="Manual §3" if estado != "Retrasado" else "Manual §2 y §3",
        )
    if estado == "Incidencia":
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="pedido_no_entregado",
            alternative="Primero hay que resolver la incidencia de entrega; un asesor "
            "contacta al cliente en un plazo máximo de 24 horas.",
            policy_reference="Manual §2",
            escalate_to_human=True,
        )
    if estado == "Devuelto":
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="devolucion_en_curso",
            alternative="Ya existe una devolución en revisión; el reembolso se procesa "
            f"en {PLAZO_REEMBOLSO} después de verificar el producto.",
            policy_reference="Manual §4.3",
            refund_timeframe=PLAZO_REEMBOLSO,
            escalate_to_human=True,
        )
    if estado == "Cancelado":
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="pedido_cancelado",
            alternative="El pedido fue cancelado, así que no hay producto que devolver; "
            "el reembolso se hace por el mismo medio de pago.",
            policy_reference="Manual §3",
        )
    # Estado desconocido: no se decide sin un humano.
    return ResultadoElegibilidad(
        eligible=False,
        rejection_reason="motivo_requiere_revision",
        alternative="Un asesor revisará el estado del pedido.",
        policy_reference="Manual §7",
        escalate_to_human=True,
    )


def evaluar_elegibilidad(pedido: dict, motivo: str, hoy: date) -> ResultadoElegibilidad:
    """Aplica el árbol de decisión de devoluciones al pedido y al motivo declarado.

    Orden: estado → motivo → vía → exclusiones → ventana → garantía del
    fabricante → devolución física. `motivo` debe ser uno de `MOTIVOS`.
    """
    if motivo not in MOTIVOS:
        raise ValueError(f"Motivo desconocido: {motivo}")

    estado = pedido.get("status")
    if estado != "Entregado":
        return _evaluar_no_entregado(estado)

    if motivo == "otro":
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="motivo_requiere_revision",
            alternative="Un asesor revisará el caso para encontrar la mejor solución.",
            policy_reference="Manual §7",
            escalate_to_human=True,
        )

    entrega = pedido.get("delivered_date")
    if not entrega:
        # Entregado sin fecha: dato inconsistente, no se adivina la ventana.
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="motivo_requiere_revision",
            alternative="Un asesor verificará la fecha de entrega del pedido.",
            policy_reference="Manual §7",
            escalate_to_human=True,
        )

    fecha_entrega = date.fromisoformat(entrega)
    calendario = max((hoy - fecha_entrega).days, 0)
    habiles = dias_habiles(fecha_entrega, hoy)
    dias = {"business_days": habiles, "calendar_days": calendario}

    if motivo in MOTIVOS_RETRACTO:
        if _excluido_de_retracto(pedido):
            return ResultadoElegibilidad(
                eligible=False,
                rejection_reason="categoria_excluida_de_retracto",
                alternative="Si el producto llegó dañado, defectuoso o no corresponde a lo "
                f"pedido, aplica la garantía de {VENTANA_GARANTIA_DIAS} días.",
                policy_reference="Manual §4.1",
                **dias,
            )
        if habiles <= VENTANA_RETRACTO_DIAS_HABILES:
            return ResultadoElegibilidad(
                eligible=True,
                return_method="retracto",
                requires_physical_return=True,
                policy_reference="Manual §4.1",
                return_window=f"{VENTANA_RETRACTO_DIAS_HABILES} días hábiles desde la entrega",
                return_process=PROCESO_RETRACTO,
                refund_timeframe=PLAZO_REEMBOLSO,
                **dias,
            )
        return ResultadoElegibilidad(
            eligible=False,
            rejection_reason="ventana_retracto_vencida",
            alternative="Si el producto presenta un defecto o llegó dañado, aplica la "
            f"garantía de {VENTANA_GARANTIA_DIAS} días.",
            policy_reference="Manual §4.1",
            return_window=f"{VENTANA_RETRACTO_DIAS_HABILES} días hábiles desde la entrega",
            **dias,
        )

    # Vía garantía.
    if calendario <= VENTANA_GARANTIA_DIAS:
        foto = _sin_devolucion_fisica(pedido)
        return ResultadoElegibilidad(
            eligible=True,
            return_method="garantia",
            requires_physical_return=not foto,
            policy_reference="Manual §4.2",
            return_window=f"{VENTANA_GARANTIA_DIAS} días calendario desde la entrega",
            return_process=PROCESO_GARANTIA_FOTO if foto else PROCESO_GARANTIA_RECOLECCION,
            refund_timeframe=PLAZO_REEMBOLSO,
            **dias,
        )
    # La garantía del fabricante cubre defectos de fabricación, no daños de
    # transporte ni productos equivocados (§5).
    if (
        pedido.get("product_category") == "Tecnología"
        and motivo == "producto_defectuoso"
        and calendario <= VENTANA_FABRICANTE_DIAS
    ):
        return ResultadoElegibilidad(
            eligible=True,
            return_method="garantia_fabricante",
            requires_physical_return=True,
            policy_reference="Manual §5",
            return_window="12 meses desde la entrega (garantía del fabricante)",
            return_process=PROCESO_FABRICANTE,
            refund_timeframe="Reparación o reemplazo según el diagnóstico",
            **dias,
        )
    return ResultadoElegibilidad(
        eligible=False,
        rejection_reason="ventana_garantia_vencida",
        alternative="Un asesor puede revisar el caso y orientar sobre otras opciones.",
        policy_reference="Manual §4.2",
        return_window=f"{VENTANA_GARANTIA_DIAS} días calendario desde la entrega",
        **dias,
    )
