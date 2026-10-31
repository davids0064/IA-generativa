"""Herramientas del agente: formato de salida, errores tipados y guardas (sin LLM)."""

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agente import herramientas as h
from src.agente import simulador
from src.agente.observabilidad import enmascarar

RAIZ = Path(__file__).resolve().parents[1]


def _ruta(archivo: str) -> Path:
    ruta = Path(archivo)
    return ruta if ruta.is_absolute() else RAIZ / ruta


# --- Convención de salida ------------------------------------------------------


def test_salida_exitosa_usa_status_y_atributos_en_ingles():
    salida = h.verificar_elegibilidad("ECO-2024-0015", "cambio_de_opinion")
    assert salida["status"] == "SUCCESS"
    assert "ok" not in salida
    for clave in ("eligible", "return_method", "requires_physical_return", "refund_timeframe",
                  "policy_reference", "eligibility_token", "days_since_delivery"):
        assert clave in salida
    assert salida["return_method"] == "retracto"  # valores en español
    assert salida["eligibility_token"].startswith("ELG-")


@pytest.mark.parametrize(
    "tracking, codigo",
    [("12345", "FORMATO_TRACKING_INVALIDO"), ("", "FORMATO_TRACKING_INVALIDO"),
     ("ECO-2099-9999", "PEDIDO_NO_ENCONTRADO")],
)
def test_errores_de_pedido(tracking, codigo):
    for salida in (h.consultar(tracking), h.verificar_elegibilidad(tracking, "producto_danado")):
        assert salida["status"] == "ERROR"
        assert salida["error_code"] == codigo
        assert salida["message"] and salida["suggested_action"]


def test_tracking_se_normaliza():
    assert h.consultar("  eco-2024-0002 ")["order"]["tracking_number"] == "ECO-2024-0002"


def test_motivo_invalido():
    salida = h.verificar_elegibilidad("ECO-2024-0015", "regalo")
    assert salida["error_code"] == "MOTIVO_INVALIDO"


def test_no_elegible_no_es_error():
    salida = h.verificar_elegibilidad("ECO-2024-0001", "cambio_de_opinion")
    assert salida["status"] == "SUCCESS"
    assert salida["eligible"] is False
    assert salida["rejection_reason"] == "categoria_excluida_de_retracto"
    assert salida["alternative"]


def test_consultar_pedido_no_expone_direccion_de_entregados():
    entregado = h.consultar("ECO-2024-0001")["order"]
    assert "current_location" not in entregado
    assert entregado["customer"] == "Ana"  # solo nombre de pila
    en_camino = h.consultar("ECO-2024-0002")["order"]
    assert "Medellín" in en_camino["current_location"]


# --- Generación de etiqueta ----------------------------------------------------


def test_etiqueta_requiere_confirmacion():
    salida = h.generar_etiqueta("ECO-2024-0015", "cambio_de_opinion", confirmado_por_cliente=False)
    assert salida["error_code"] == "CONFIRMACION_REQUERIDA"
    assert simulador.buscar_rma("ECO-2024-0015") is None


def test_etiqueta_recalcula_elegibilidad_aunque_el_llm_insista():
    salida = h.generar_etiqueta("ECO-2024-0001", "cambio_de_opinion", confirmado_por_cliente=True)
    assert salida["status"] == "ERROR"
    assert salida["error_code"] == "NO_ELEGIBLE"
    assert salida["rejection_reason"] == "categoria_excluida_de_retracto"
    assert simulador.buscar_rma("ECO-2024-0001") is None


def test_etiqueta_con_recoleccion_genera_pdf():
    salida = h.generar_etiqueta("ECO-2024-0015", "cambio_de_opinion", confirmado_por_cliente=True)
    assert salida["status"] == "SUCCESS"
    assert salida["rma"].startswith("RMA-2026-")
    assert salida["return_type"] == "recoleccion"
    assert salida["waybill_number"].endswith("CO")
    assert salida["already_existed"] is False
    pdf = _ruta(salida["label_file"])
    assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF")


def test_etiqueta_es_idempotente():
    primera = h.generar_etiqueta("ECO-2024-0015", "cambio_de_opinion", True)
    segunda = h.generar_etiqueta("ECO-2024-0015", "talla_incorrecta", True)
    assert segunda["rma"] == primera["rma"]
    assert segunda["already_existed"] is True
    registros = json.loads((simulador.directorio_operacion() / "devoluciones.json").read_text())
    assert len(registros) == 1


def test_garantia_sin_devolucion_fisica():
    salida = h.generar_etiqueta("ECO-2024-0013", "producto_danado", True)
    assert salida["return_type"] == "sin_devolucion_fisica"
    assert salida["label_file"] is None
    assert any("foto" in paso for paso in salida["instructions"])


def test_falla_de_transportadora_no_persiste_nada(monkeypatch):
    monkeypatch.setenv("SIMULAR_FALLA_TRANSPORTADORA", "true")
    salida = h.generar_etiqueta("ECO-2024-0015", "cambio_de_opinion", True)
    assert salida["error_code"] == "SERVICIO_TRANSPORTADORA_NO_DISPONIBLE"
    assert salida["eligible"] is True
    assert "escalar_a_humano" in salida["suggested_action"]
    assert simulador.buscar_rma("ECO-2024-0015") is None


def test_falla_solo_para_trackings_indicados(monkeypatch):
    monkeypatch.setenv("TRACKINGS_CON_FALLA", "ECO-2024-0008")
    assert h.generar_etiqueta("ECO-2024-0008", "producto_defectuoso", True)["status"] == "ERROR"
    assert h.generar_etiqueta("ECO-2024-0015", "cambio_de_opinion", True)["status"] == "SUCCESS"


# --- Confirmación verificada en la conversación --------------------------------


def _verificacion(tracking="ECO-2024-0015", elegible=True) -> list:
    llamada = {"name": "verificar_elegibilidad_producto", "id": "c1",
               "args": {"tracking_number": tracking, "motivo": "cambio_de_opinion"}}
    return [
        HumanMessage("Quiero devolver la camiseta del pedido ECO-2024-0015, no me gustó"),
        AIMessage("", tool_calls=[llamada]),
        ToolMessage("{}", tool_call_id="c1", name="verificar_elegibilidad_producto",
                    artifact={"status": "SUCCESS", "eligible": elegible, "tracking_number": tracking}),
        AIMessage("Tu camiseta se puede devolver con recolección gratuita. ¿Confirmas?"),
    ]


@pytest.mark.parametrize("respuesta", ["Sí, confirmo", "si", "Dale, hazlo", "ok, perfecto",
                                       "Sí, no hay problema"])
def test_confirmacion_valida(respuesta):
    assert h.confirmacion_en_conversacion(_verificacion() + [HumanMessage(respuesta)], "ECO-2024-0015")


@pytest.mark.parametrize("respuesta", ["No", "no, mejor no", "¿Cuánto tarda el reembolso?",
                                       "todavía no"])
def test_respuesta_que_no_confirma(respuesta):
    assert not h.confirmacion_en_conversacion(_verificacion() + [HumanMessage(respuesta)], "ECO-2024-0015")


def test_confirmacion_inventada_por_el_llm_en_el_mismo_turno():
    # El cliente pidió la devolución y el LLM verificó y quiso generar la etiqueta sin preguntar.
    mensajes = _verificacion()[:3]
    assert not h.confirmacion_en_conversacion(mensajes, "ECO-2024-0015")
    salida = h.generar_etiqueta("ECO-2024-0015", "cambio_de_opinion", True, mensajes)
    assert salida["error_code"] == "CONFIRMACION_REQUERIDA"


def test_confirmacion_de_otro_pedido_o_no_elegible():
    mensajes = _verificacion(tracking="ECO-2024-0008") + [HumanMessage("sí")]
    assert not h.confirmacion_en_conversacion(mensajes, "ECO-2024-0015")
    mensajes = _verificacion(elegible=False) + [HumanMessage("sí")]
    assert not h.confirmacion_en_conversacion(mensajes, "ECO-2024-0015")


# --- Herramientas como objetos de LangChain ------------------------------------


def _invocar(herramienta, **args) -> ToolMessage:
    return herramienta.invoke({"type": "tool_call", "id": "t1", "name": herramienta.name, "args": args})


def test_argumentos_fuera_del_esquema_devuelven_error_estructurado():
    mensaje = _invocar(h.verificar_elegibilidad_producto, tracking_number="ECO-2024-0015", motivo="regalo")
    contenido = json.loads(mensaje.content)
    assert contenido["status"] == "ERROR"
    assert contenido["error_code"] == "ARGUMENTOS_INVALIDOS"


def test_herramienta_entrega_json_al_llm_y_dict_a_la_interfaz():
    mensaje = _invocar(h.consultar_pedido, tracking_number="ECO-2024-0002")
    assert json.loads(mensaje.content)["order"]["order_status"] == "En tránsito"
    assert mensaje.artifact["status"] == "SUCCESS"


def test_runtime_no_aparece_en_el_esquema_del_llm():
    propiedades = h.generar_etiqueta_devolucion.tool_call_schema.model_json_schema()["properties"]
    assert set(propiedades) == {"tracking_number", "motivo", "confirmado_por_cliente"}


def test_base_de_conocimiento_caida(monkeypatch):
    def caida(*args, **kwargs):
        raise ConnectionError("chroma caído")

    monkeypatch.setattr(h.rag, "recuperar", caida)
    assert h.consultar_base("¿Cuánto tarda el reembolso?")["error_code"] == "BASE_CONOCIMIENTO_NO_DISPONIBLE"
    monkeypatch.setattr(h.rag, "recuperar", lambda *a, **k: [])
    assert h.consultar_base("algo")["error_code"] == "SIN_RESULTADOS"


def test_error_inesperado_se_convierte_en_error_interno(monkeypatch):
    def rota(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(h.db, "buscar_pedido", rota)
    contenido = json.loads(_invocar(h.consultar_pedido, tracking_number="ECO-2024-0002").content)
    assert contenido["error_code"] == "ERROR_INTERNO"


def test_escalar_crea_ticket():
    salida = h.escalar("molestia", "Cliente molesto por demora", "eco-2024-0004")
    assert salida["status"] == "SUCCESS"
    assert salida["ticket_id"].startswith("TCK-2026-")
    ticket = json.loads((simulador.directorio_operacion() / "tickets.json").read_text())[0]
    assert ticket["tracking_number"] == "ECO-2024-0004"


def test_enmascarar_pii():
    texto = enmascarar("Escríbeme a ana@correo.com o al +57 300 123 4567, pedido ECO-2024-0001")
    assert "ana@correo.com" not in texto and "300 123 4567" not in texto
    assert "ECO-2024-0001" in texto
