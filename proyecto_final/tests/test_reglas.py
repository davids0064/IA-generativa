"""Árbol de decisión de devoluciones sobre todo el dataset (fecha de referencia 2026-09-29)."""

from datetime import date

import pytest

from src import db
from src.agente.reglas import MOTIVOS, dias_habiles, evaluar_elegibilidad

HOY = date(2026, 9, 29)

# (tracking, motivo, eligible, return_method o rejection_reason, requires_physical_return)
CASOS = [
    # Higiene personal entregado hace 30 días: excluido del retracto, garantía sin devolución física.
    ("ECO-2024-0001", "cambio_de_opinion", False, "categoria_excluida_de_retracto", None),
    ("ECO-2024-0001", "talla_incorrecta", False, "categoria_excluida_de_retracto", None),
    ("ECO-2024-0001", "producto_danado", True, "garantia", False),
    ("ECO-2024-0001", "producto_defectuoso", True, "garantia", False),
    ("ECO-2024-0001", "producto_equivocado", True, "garantia", False),
    ("ECO-2024-0001", "otro", False, "motivo_requiere_revision", None),
    # Pedidos que aún no se entregan.
    ("ECO-2024-0002", "producto_danado", False, "pedido_no_entregado", None),  # En tránsito
    ("ECO-2024-0003", "cambio_de_opinion", False, "pedido_no_entregado", None),  # Procesando
    ("ECO-2024-0004", "producto_danado", False, "pedido_no_entregado", None),  # Retrasado
    ("ECO-2024-0005", "cambio_de_opinion", False, "pedido_no_entregado", None),  # En reparto
    ("ECO-2024-0007", "producto_defectuoso", False, "pedido_no_entregado", None),  # En tránsito
    ("ECO-2024-0010", "talla_incorrecta", False, "pedido_no_entregado", None),  # Procesando
    ("ECO-2024-0011", "producto_danado", False, "pedido_no_entregado", None),  # Incidencia
    ("ECO-2024-0012", "producto_danado", False, "pedido_no_entregado", None),  # En reparto
    # Devuelto y cancelado.
    ("ECO-2024-0006", "producto_danado", False, "devolucion_en_curso", None),
    ("ECO-2024-0009", "cambio_de_opinion", False, "pedido_cancelado", None),
    # Panel solar entregado hace 22 días (16 hábiles): retracto vencido, garantía vigente.
    ("ECO-2024-0008", "cambio_de_opinion", False, "ventana_retracto_vencida", None),
    ("ECO-2024-0008", "producto_defectuoso", True, "garantia", True),
    # Perecedero entregado hace 22 días.
    ("ECO-2024-0013", "cambio_de_opinion", False, "categoria_excluida_de_retracto", None),
    ("ECO-2024-0013", "producto_danado", True, "garantia", False),
    # Textil entregado hace 105 días: todas las ventanas vencidas.
    ("ECO-2024-0014", "cambio_de_opinion", False, "ventana_retracto_vencida", None),
    ("ECO-2024-0014", "producto_danado", False, "ventana_garantia_vencida", None),
    ("ECO-2024-0014", "producto_defectuoso", False, "ventana_garantia_vencida", None),
    # Textil entregado hace 2 días hábiles: retracto con recolección.
    ("ECO-2024-0015", "cambio_de_opinion", True, "retracto", True),
    ("ECO-2024-0015", "talla_incorrecta", True, "retracto", True),
    # Tecnología entregada hace 137 días: solo el defecto de fabricación tiene garantía del fabricante.
    ("ECO-2024-0016", "producto_defectuoso", True, "garantia_fabricante", True),
    ("ECO-2024-0016", "producto_danado", False, "ventana_garantia_vencida", None),
    ("ECO-2024-0016", "cambio_de_opinion", False, "ventana_retracto_vencida", None),
]


@pytest.mark.parametrize("tracking, motivo, elegible, via_o_rechazo, fisica", CASOS)
def test_elegibilidad_dataset(tracking, motivo, elegible, via_o_rechazo, fisica):
    resultado = evaluar_elegibilidad(db.buscar_pedido(tracking), motivo, HOY)
    assert resultado.eligible is elegible
    if elegible:
        assert resultado.return_method == via_o_rechazo
        assert resultado.requires_physical_return is fisica
        assert resultado.refund_timeframe
        assert resultado.rejection_reason is None
    else:
        assert resultado.rejection_reason == via_o_rechazo
        assert resultado.alternative, "toda negativa debe ofrecer una alternativa"
        assert resultado.return_method is None
    assert resultado.policy_reference.startswith("Manual §")


def test_todo_el_dataset_tiene_veredicto_para_cada_motivo():
    for pedido in db.cargar_pedidos():
        for motivo in MOTIVOS:
            assert evaluar_elegibilidad(pedido, motivo, HOY).policy_reference


@pytest.mark.parametrize(
    "tracking, motivo",
    [
        ("ECO-2024-0006", "producto_danado"),  # Devuelto
        ("ECO-2024-0011", "producto_danado"),  # Incidencia
        ("ECO-2024-0015", "otro"),
    ],
)
def test_casos_que_escalan_a_humano(tracking, motivo):
    assert evaluar_elegibilidad(db.buscar_pedido(tracking), motivo, HOY).escalate_to_human


def _pedido(entrega: str, categoria="Hogar", perecedero=False, higiene=False) -> dict:
    return {
        "status": "Entregado",
        "delivered_date": entrega,
        "product_category": categoria,
        "is_perishable": perecedero,
        "is_hygiene_item": higiene,
    }


def test_limite_ventana_retracto_en_dias_habiles():
    # Lunes 2026-09-21 → lunes 2026-09-28 son 5 días hábiles; martes 29, 6.
    assert evaluar_elegibilidad(_pedido("2026-09-21"), "cambio_de_opinion", date(2026, 9, 28)).eligible
    assert not evaluar_elegibilidad(_pedido("2026-09-21"), "cambio_de_opinion", date(2026, 9, 29)).eligible


def test_limite_ventana_garantia_en_dias_calendario():
    assert evaluar_elegibilidad(_pedido("2026-08-30"), "producto_danado", HOY).eligible  # 30 días
    assert not evaluar_elegibilidad(_pedido("2026-08-29"), "producto_danado", HOY).eligible  # 31 días


def test_limite_garantia_fabricante():
    tec = "Tecnología"
    assert evaluar_elegibilidad(_pedido("2025-10-04", tec), "producto_defectuoso", HOY).eligible  # 360
    assert not evaluar_elegibilidad(_pedido("2025-10-03", tec), "producto_defectuoso", HOY).eligible


def test_suscripcion_excluida_de_retracto():
    pedido = _pedido("2026-09-28", "Suscripción", perecedero=True)
    resultado = evaluar_elegibilidad(pedido, "cambio_de_opinion", HOY)
    assert resultado.rejection_reason == "categoria_excluida_de_retracto"


def test_entregado_sin_fecha_requiere_revision():
    resultado = evaluar_elegibilidad(_pedido(None), "producto_danado", HOY)
    assert resultado.rejection_reason == "motivo_requiere_revision"
    assert resultado.escalate_to_human


def test_motivo_desconocido():
    with pytest.raises(ValueError):
        evaluar_elegibilidad(_pedido("2026-09-28"), "regalo", HOY)


def test_dias_habiles_excluye_fines_de_semana():
    assert dias_habiles(date(2026, 9, 25), date(2026, 9, 29)) == 2  # viernes → martes
    assert dias_habiles(date(2026, 9, 26), date(2026, 9, 27)) == 0  # sábado → domingo
    assert dias_habiles(date(2026, 9, 29), date(2026, 9, 29)) == 0
