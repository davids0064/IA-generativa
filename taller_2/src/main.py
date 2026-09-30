"""Agente de atención al cliente de EcoMarket.

Taller 1 (Fase 3, ejercicio 1): ejecuta el prompt básico y el mejorado sobre el
mismo número de seguimiento para evidenciar el impacto de la ingeniería de
prompts.

Taller 2 (Fase 3): el modo `rag` añade la base de conocimiento (políticas,
catálogo y FAQ) recuperada con LangChain + ChromaDB, de modo que el agente
también responde preguntas abiertas que no están en el registro del pedido.
El índice se carga una sola vez con `python -m src.base_conocimiento`; aquí
solo se consulta.

Ejemplos de uso:
    python -m src.main --tracking ECO-2024-0004
    python -m src.main --tracking ECO-2024-0004 --modo basico
    python -m src.main --tracking ECO-2024-0004 --modo mejorado
    python -m src.main --listar
    python -m src.main --modo rag --consulta "¿Puedo devolver un jabón que ya abrí?"
    python -m src.main --modo rag --tracking ECO-2024-0004 --consulta "¿Me devuelven el envío por el retraso?"
"""

import argparse
import json
import textwrap

from langchain_core.exceptions import OutputParserException

from src import base_conocimiento, db, llm, prompts, rag

ANCHO = 78


def _titulo(texto: str) -> None:
    print(f"\n{'=' * ANCHO}\n{texto}\n{'=' * ANCHO}")


def _parrafo(texto: str) -> str:
    return textwrap.fill(texto, width=ANCHO)


def ejecutar_basico(tracking_number: str) -> str:
    """Envía el prompt básico: solo la pregunta, sin datos del pedido."""
    mensajes = prompts.construir_mensajes_basico(tracking_number)
    _titulo("PROMPT BÁSICO")
    print(f"Enviado al modelo:\n  {mensajes[0]['content']}\n")
    respuesta = llm.completar(mensajes)
    print("Respuesta del modelo:")
    print(_parrafo(respuesta))
    return respuesta


def ejecutar_mejorado(tracking_number: str, consulta: str | None = None) -> dict:
    """Recupera el pedido (RAG) y envía el prompt mejorado."""
    pedido = db.buscar_pedido(tracking_number)
    registro = db.formatear_para_prompt(pedido, campos=db.CAMPOS_PEDIDO)
    consulta = consulta or f"Dame el estado del pedido {tracking_number}."

    mensajes = prompts.construir_mensajes_mejorado(consulta, registro)

    _titulo("PROMPT MEJORADO")
    print(f"Consulta del cliente:\n  {consulta}")
    print(f"\nContexto recuperado de la base de datos:\n{registro or '  (sin resultados)'}\n")

    cruda = llm.completar(mensajes, formato_json=True)
    try:
        salida = json.loads(cruda)
    except json.JSONDecodeError:
        print("El modelo no devolvió un JSON válido. Salida sin procesar:")
        print(_parrafo(cruda))
        return {}

    print("Respuesta estructurada:")
    print(f"  order_found       : {salida.get('order_found')}")
    print(f"  status            : {salida.get('status')}")
    print(f"  escalate_to_human : {salida.get('escalate_to_human')}")
    print(f"  reasoning         : {salida.get('reasoning')}")
    print("\nMensaje entregado al cliente:")
    print(_parrafo(salida.get("customer_response", "")))
    return salida


def ejecutar_rag(consulta: str | None, tracking_number: str | None = None) -> dict:
    """Recupera pedido + base de conocimiento y responde con la cadena RAG."""
    consulta = consulta or f"Dame el estado del pedido {tracking_number}."

    _titulo("AGENTE CON RAG (LangChain + ChromaDB)")
    print(f"Consulta del cliente:\n  {consulta}")

    try:
        resultado = rag.responder(consulta, tracking_number)
    except OutputParserException as error:
        print("El modelo no devolvió un JSON válido. Salida sin procesar:")
        print(_parrafo(str(error.llm_output)))
        return {}

    print(f"\nPedido asociado:\n{resultado['registro_json'] or '  (ninguno)'}")
    print("\nFragmentos recuperados de la base de conocimiento:")
    for i, doc in enumerate(resultado["documentos"], start=1):
        primera_linea = doc.page_content.strip().splitlines()[0][:60]
        print(f"  [{i}] {rag._etiqueta(doc):<45} {primera_linea}")

    salida = resultado["respuesta"]
    print("\nRespuesta estructurada:")
    print(f"  order_found       : {salida.get('order_found')}")
    print(f"  status            : {salida.get('status')}")
    print(f"  answer_grounded   : {salida.get('answer_grounded')}")
    print(f"  sources_used      : {salida.get('sources_used')}")
    print(f"  escalate_to_human : {salida.get('escalate_to_human')}")
    print(f"  reasoning         : {salida.get('reasoning')}")
    print("\nMensaje entregado al cliente:")
    print(_parrafo(salida.get("customer_response", "")))
    return salida


def listar_pedidos() -> None:
    """Muestra los pedidos disponibles en la base de datos simulada."""
    _titulo("PEDIDOS EN LA BASE DE DATOS")
    for pedido in db.cargar_pedidos():
        print(f"  {pedido['tracking_number']}  {pedido['status']:<12}  {pedido['customer']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking", help="Número de seguimiento a consultar")
    parser.add_argument(
        "--modo",
        choices=("basico", "mejorado", "ambos", "rag"),
        default="ambos",
        help="Versión del agente a ejecutar (por defecto: ambos = básico + mejorado)",
    )
    parser.add_argument("--consulta", help="Texto libre del cliente (modos mejorado y rag)")
    parser.add_argument("--listar", action="store_true", help="Lista los pedidos disponibles")
    args = parser.parse_args()

    if args.listar:
        listar_pedidos()
        return

    if args.modo == "rag":
        if not (args.tracking or args.consulta):
            parser.error("el modo rag requiere --consulta, --tracking o ambos")
        base_conocimiento.verificar_indice()
        ejecutar_rag(args.consulta, args.tracking)
        return

    if not args.tracking:
        parser.error("indica un número de seguimiento con --tracking o usa --listar")

    if args.modo in ("basico", "ambos"):
        ejecutar_basico(args.tracking)
    if args.modo in ("mejorado", "ambos"):
        ejecutar_mejorado(args.tracking, args.consulta)


if __name__ == "__main__":
    main()
