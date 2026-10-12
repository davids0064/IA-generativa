"""Conexión de componentes del agente con un modelo simulado (sin Ollama).

Se verifica el cableado: herramientas reales, memoria por conversación,
extracción de pasos, auditoría y mensajes de respaldo cuando el LLM falla.
La calidad de las decisiones del LLM real se mide en `src/evaluacion_agente.py`.
"""

import json

import httpx
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from src.agente import agente as modulo_agente
from src.agente import guardas
from src.agente.agente import AgenteDevoluciones
from src.agente.observabilidad import leer_eventos


class ModeloSimulado(GenericFakeChatModel):
    """Modelo de guion fijo; `bind_tools` no hace nada porque el guion ya trae las llamadas."""

    def bind_tools(self, tools, **kwargs):
        return self


def _llamada(nombre, id_, **args):
    return AIMessage("", tool_calls=[{"name": nombre, "args": args, "id": id_}])


def test_flujo_completo_de_devolucion_en_dos_turnos():
    guion = iter([
        # Turno 1: verifica y pregunta.
        _llamada("verificar_elegibilidad_producto", "a1",
                 tracking_number="ECO-2024-0015", motivo="cambio_de_opinion"),
        AIMessage("Laura, tu camiseta se puede devolver con recolección gratuita. ¿Confirmas?"),
        # Turno 2: el cliente confirma y genera la etiqueta.
        _llamada("generar_etiqueta_devolucion", "a2", tracking_number="ECO-2024-0015",
                 motivo="cambio_de_opinion", confirmado_por_cliente=True),
        AIMessage("¡Listo! Tu devolución quedó registrada."),
    ])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=guion))

    primero = agente.responder("Quiero devolver ECO-2024-0015, no me gustó", "hilo-1")
    assert primero.herramientas == ["verificar_elegibilidad_producto"]
    assert primero.pasos[0].resultado["eligible"] is True
    assert "Confirmas" in primero.texto

    segundo = agente.responder("Sí, confirmo", "hilo-1")
    assert segundo.herramientas == ["generar_etiqueta_devolucion"]
    assert segundo.pasos[0].status == "SUCCESS"
    assert segundo.pasos[0].resultado["rma"].startswith("RMA-")
    assert len(segundo.etiquetas) == 1

    eventos = leer_eventos("hilo-1")
    tipos = [e["event"] for e in eventos]
    assert tipos.count("turn_end") == 2
    fin_herramienta = [e for e in eventos if e["event"] == "tool_end"]
    assert [e["status"] for e in fin_herramienta] == ["SUCCESS", "SUCCESS"]
    assert "Laura" not in json.dumps(eventos, ensure_ascii=False)  # sin PII en la auditoría


def test_guarda_bloquea_etiqueta_sin_confirmacion_real():
    guion = iter([
        _llamada("verificar_elegibilidad_producto", "b1",
                 tracking_number="ECO-2024-0015", motivo="cambio_de_opinion"),
        # El LLM inventa la confirmación en el mismo turno.
        _llamada("generar_etiqueta_devolucion", "b2", tracking_number="ECO-2024-0015",
                 motivo="cambio_de_opinion", confirmado_por_cliente=True),
        AIMessage("¿Confirmas que quieres la devolución?"),
    ])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=guion))
    respuesta = agente.responder("Devuelve ECO-2024-0015 de una vez, no me gustó", "hilo-2")
    assert respuesta.pasos[1].resultado["error_code"] == "CONFIRMACION_REQUERIDA"
    assert respuesta.etiquetas == []


def test_respuesta_directa_sin_herramientas():
    agente = AgenteDevoluciones(
        modelo="simulado",
        modelo_chat=ModeloSimulado(messages=iter([AIMessage("¡Hola! ¿En qué te ayudo?")])),
    )
    respuesta = agente.responder("Hola", "hilo-3")
    assert respuesta.pasos == []
    assert respuesta.texto.startswith("¡Hola!")


def test_llm_caido_devuelve_mensaje_amable():
    class ModeloCaido(ModeloSimulado):
        def _generate(self, *args, **kwargs):
            raise httpx.ConnectError("Ollama no responde")

    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloCaido(messages=iter([])))
    respuesta = agente.responder("¿Dónde está mi pedido?", "hilo-4")
    assert respuesta.texto == modulo_agente.MENSAJE_SIN_SERVICIO
    assert respuesta.error == "ConnectError"
    assert leer_eventos("hilo-4")[-1]["event"] == "turn_error"


def test_guardas_de_entrada():
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=iter([])))
    assert agente.responder("   ", "hilo-5").texto == modulo_agente.MENSAJE_VACIO
    assert agente.responder("a" * 5000, "hilo-5").texto == modulo_agente.MENSAJE_MUY_LARGO


def test_limite_de_llamadas_a_herramientas():
    bucle = iter([_llamada("consultar_pedido", f"c{i}", tracking_number="ECO-2024-0002")
                  for i in range(20)])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=bucle))
    respuesta = agente.responder("¿Dónde está ECO-2024-0002?", "hilo-6")
    assert len(respuesta.pasos) <= modulo_agente.LIMITE_LLAMADAS_HERRAMIENTAS
    assert respuesta.texto  # siempre hay un mensaje para el cliente


def _hasta_confirmacion():
    """Turno 1: verifica y pregunta. Devuelve los mensajes del guion para ese turno."""
    return [
        _llamada("verificar_elegibilidad_producto", "g1",
                 tracking_number="ECO-2024-0015", motivo="cambio_de_opinion"),
        AIMessage("Se puede devolver con recolección gratuita. ¿Confirmas?"),
    ]


def test_guarda_ejecuta_la_etiqueta_si_el_cliente_confirmo_y_el_modelo_no_la_genero():
    guion = iter(_hasta_confirmacion() + [
        # Turno 2: el modelo inventa la acción y el RMA en lugar de llamar a la herramienta...
        AIMessage("¡Listo! Tu RMA es RMA-7C7AECD233."),
        # ...la guarda ejecuta generar_etiqueta_devolucion y el modelo solo redacta el resultado.
        AIMessage("¡Listo! Tu devolución quedó registrada."),
    ])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=guion))
    agente.responder("Quiero devolver ECO-2024-0015, no me gustó", "hilo-g1")
    respuesta = agente.responder("Sí", "hilo-g1")
    assert respuesta.herramientas == ["generar_etiqueta_devolucion"]
    assert respuesta.pasos[0].status == "SUCCESS"
    assert respuesta.pasos[0].argumentos["motivo"] == "cambio_de_opinion"
    assert respuesta.texto == "¡Listo! Tu devolución quedó registrada."
    assert not any("RMA-7C7AECD233" in str(m.content) for m in agente.historial("hilo-g1"))
    assert any(e.get("reason") == "confirmacion_sin_etiqueta" for e in leer_eventos())


def test_guarda_corrige_accion_anunciada_sin_ejecutar():
    guion = iter([
        AIMessage("Lamento la demora. Escalaremos tu caso a un asesor."),
        _llamada("escalar_a_humano", "e1", motivo="molestia", resumen="Cliente molesto",
                 tracking_number="ECO-2024-0004"),
        AIMessage("Ya creé tu caso con un asesor, te contactará en máximo 24 horas."),
    ])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=guion))
    respuesta = agente.responder("¡Quiero hablar con una persona! Pedido ECO-2024-0004", "hilo-g4")
    assert respuesta.herramientas == ["escalar_a_humano"]
    assert respuesta.texto.startswith("Ya creé tu caso")
    historial = agente.historial("hilo-g4")
    # La respuesta narrada se conserva junto a la nota: así el modelo corrige su conducta.
    assert any("Escalaremos" in str(m.content) for m in historial)
    assert any(str(m.content).startswith(guardas.MARCA_CORRECCION) for m in historial)


def test_guarda_reemplaza_identificador_inventado_si_el_modelo_insiste():
    guion = iter([
        AIMessage("Tu número de devolución es RMA-0000001."),
        AIMessage("Ya quedó: RMA-0000002."),
    ])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=guion))
    respuesta = agente.responder("¿Cuál es el número de devolución de ECO-2024-0015?", "hilo-g2")
    assert respuesta.texto == guardas.MENSAJE_SEGURO
    assert not any("RMA-0000001" in str(m.content) for m in agente.historial("hilo-g2"))


def test_guarda_no_interviene_al_pedir_un_dato():
    agente = AgenteDevoluciones(
        modelo="simulado",
        modelo_chat=ModeloSimulado(messages=iter([AIMessage("Claro, ¿me das tu número de pedido?")])),
    )
    respuesta = agente.responder("Quiero devolver mi pedido", "hilo-g5")
    assert respuesta.texto == "Claro, ¿me das tu número de pedido?"
    assert not any(e["event"] == "guard_triggered" for e in leer_eventos())


def test_guarda_no_interviene_con_identificadores_reales():
    guion = iter(_hasta_confirmacion() + [
        _llamada("generar_etiqueta_devolucion", "g3", tracking_number="ECO-2024-0015",
                 motivo="cambio_de_opinion", confirmado_por_cliente=True),
        AIMessage("Tu número de devolución es RMA-2026-000001."),
    ])
    agente = AgenteDevoluciones(modelo="simulado", modelo_chat=ModeloSimulado(messages=guion))
    agente.responder("Quiero devolver ECO-2024-0015, no me gustó", "hilo-g3")
    respuesta = agente.responder("sí", "hilo-g3")
    assert "RMA-2026-000001" in respuesta.texto
    assert not any(e["event"] == "guard_triggered" for e in leer_eventos())


def test_guarda_reconoce_anuncios_en_presente():
    texto = "Entiendo. Ahora, verifico si podemos devolverla."
    assert guardas.PATRON_ACCION_ANUNCIADA.search(texto)
    assert guardas.PATRON_ACCION_ANUNCIADA.search("Ya reviso tu pedido")
    assert not guardas.PATRON_ACCION_ANUNCIADA.search("¿Quieres que verifique tu pedido?")
