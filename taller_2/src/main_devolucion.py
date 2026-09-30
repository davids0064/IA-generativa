"""Ejercicio 2 de la Fase 3: solicitud de devolución de un producto.

Runner independiente del ejercicio 1 (`src/main.py`) para poder probar el
prompt de devoluciones por separado. Reutiliza el mismo cliente de Ollama
(`src/llm.py`) y la misma base de datos simulada (`src/db.py`).

Taller 2 (Fase 3): el modo `rag` deja de escribir la política en el prompt y
la recupera del manual indexado en ChromaDB (ver `rag.construir_cadena_devolucion`);
la respuesta añade las citas usadas (`sources_used`). El índice se carga una
sola vez con `uv run python -m src.base_conocimiento`; aquí solo se consulta.

Ejemplos de uso:
    uv run python -m src.main_devolucion --tracking ECO-2024-0008
    uv run python -m src.main_devolucion --tracking ECO-2024-0001 --motivo producto_danado
    uv run python -m src.main_devolucion --todos --motivo cambio_de_opinion
    uv run python -m src.main_devolucion --listar
    uv run python -m src.main_devolucion --modo rag --tracking ECO-2024-0008 --motivo producto_defectuoso
    uv run python -m src.main_devolucion --modo rag --todos --motivo cambio_de_opinion
"""

import argparse
import json
import textwrap
from datetime import date, timedelta

from langchain_core.exceptions import OutputParserException

from src import base_conocimiento, db, llm, prompts_devolucion, rag

ANCHO = 78

MOTIVOS = (
    "cambio_de_opinion",
    "talla_incorrecta",
    "producto_danado",
    "producto_defectuoso",
    "producto_equivocado",
    "otro",
)

# Mensaje del cliente que se usa cuando no se pasa --consulta, para que el
# prompt siempre reciba lenguaje natural y no solo la etiqueta del motivo.
CONSULTAS_POR_MOTIVO = {
    "cambio_de_opinion": "Quiero devolver el producto de mi pedido {tracking}, cambié de opinión.",
    "talla_incorrecta": "La talla del producto de mi pedido {tracking} no me quedó, ¿puedo devolverlo?",
    "producto_danado": "El producto de mi pedido {tracking} llegó dañado, quiero devolverlo.",
    "producto_defectuoso": "El producto de mi pedido {tracking} no funciona bien, ¿qué puedo hacer?",
    "producto_equivocado": "Me llegó un producto distinto al que pedí en el pedido {tracking}.",
    "otro": "Tengo un inconveniente con mi pedido {tracking} y quiero devolverlo.",
}


def _titulo(texto: str) -> None:
    print(f"\n{'=' * ANCHO}\n{texto}\n{'=' * ANCHO}")


def _parrafo(texto: str) -> str:
    return textwrap.fill(texto, width=ANCHO)


def dias_habiles(desde: date, hasta: date) -> int:
    """Cuenta los días hábiles transcurridos entre dos fechas, sin contar `desde`.

    Solo excluye sábados y domingos: los festivos colombianos quedan fuera del
    alcance del taller y en producción vendrían de un calendario oficial.
    """
    dias = 0
    cursor = desde + timedelta(days=1)
    while cursor <= hasta:
        if cursor.weekday() < 5:
            dias += 1
        cursor += timedelta(days=1)
    return dias


def construir_contexto_temporal(pedido: dict | None, hoy: date) -> str:
    """Precalcula los días transcurridos desde la entrega.

    La aritmética de fechas es donde más se equivocan los modelos pequeños, así
    que el prompt recibe el resultado ya resuelto y solo compara contra las
    ventanas de la política.
    """
    contexto = {
        "fecha_actual": hoy.isoformat(),
        "dias_calendario_desde_entrega": None,
        "dias_habiles_desde_entrega": None,
    }
    entrega = (pedido or {}).get("delivered_date")
    if entrega:
        fecha_entrega = date.fromisoformat(entrega)
        contexto["dias_calendario_desde_entrega"] = (hoy - fecha_entrega).days
        contexto["dias_habiles_desde_entrega"] = dias_habiles(fecha_entrega, hoy)
    return json.dumps(contexto, ensure_ascii=False)


def solicitar_devolucion(
    tracking_number: str,
    motivo: str,
    consulta: str | None = None,
    hoy: date | None = None,
    modo: str = "prompt",
) -> dict:
    """Recupera el pedido (RAG), arma el prompt y devuelve la salida estructurada.

    En modo `rag` la salida incluye además `_documentos`, los fragmentos de la
    base de conocimiento que recibió el modelo.
    """
    hoy = hoy or date.today()
    pedido = db.buscar_pedido(tracking_number)
    registro = db.formatear_para_prompt(pedido, campos=db.CAMPOS_DEVOLUCION)
    contexto_temporal = construir_contexto_temporal(pedido, hoy)
    consulta = consulta or CONSULTAS_POR_MOTIVO[motivo].format(tracking=tracking_number)

    if modo == "rag":
        try:
            resultado = rag.responder_devolucion(
                consulta, motivo, tracking_number, contexto_temporal
            )
        except OutputParserException as error:
            return {"_error": "El modelo no devolvió un JSON válido", "_salida": str(error.llm_output)}
        return {**resultado["respuesta"], "_documentos": resultado["documentos"]}

    mensajes = prompts_devolucion.construir_mensajes_devolucion(
        consulta=consulta,
        motivo=motivo,
        contexto_temporal=contexto_temporal,
        registro_json=registro,
    )

    cruda = llm.completar(mensajes, formato_json=True)
    try:
        return json.loads(cruda)
    except json.JSONDecodeError:
        return {"_error": "El modelo no devolvió un JSON válido", "_salida": cruda}


def ejecutar(
    tracking_number: str,
    motivo: str,
    consulta: str | None = None,
    hoy: date | None = None,
    modo: str = "prompt",
) -> dict:
    """Ejecuta una solicitud e imprime el detalle completo de la interacción."""
    hoy = hoy or date.today()
    pedido = db.buscar_pedido(tracking_number)
    registro = db.formatear_para_prompt(pedido, campos=db.CAMPOS_DEVOLUCION)
    contexto_temporal = construir_contexto_temporal(pedido, hoy)
    consulta_final = consulta or CONSULTAS_POR_MOTIVO[motivo].format(tracking=tracking_number)

    sufijo = " (RAG)" if modo == "rag" else ""
    _titulo(f"SOLICITUD DE DEVOLUCIÓN{sufijo} — {tracking_number}")
    print(f"Consulta del cliente:\n  {consulta_final}")
    print(f"\nMotivo declarado:\n  {motivo}")
    print(f"\nContexto temporal inyectado:\n  {contexto_temporal}")
    print(f"\nContexto recuperado de la base de datos:\n{registro or '  (sin resultados)'}\n")

    salida = solicitar_devolucion(tracking_number, motivo, consulta_final, hoy, modo)
    if "_error" in salida:
        print(f"{salida['_error']}. Salida sin procesar:")
        print(_parrafo(salida["_salida"]))
        return salida

    if modo == "rag":
        print("Fragmentos recuperados de la base de conocimiento:")
        for i, doc in enumerate(salida["_documentos"], start=1):
            primera_linea = doc.page_content.strip().splitlines()[0][:60]
            print(f"  [{i}] {rag._etiqueta(doc):<45} {primera_linea}")
        print()

    print("Respuesta estructurada:")
    print(f"  order_found               : {salida.get('order_found')}")
    print(f"  order_status              : {salida.get('order_status')}")
    print(f"  classified_reason         : {salida.get('classified_reason')}")
    print(f"  return_eligible           : {salida.get('return_eligible')}")
    print(f"  return_method             : {salida.get('return_method')}")
    print(f"  requires_physical_return  : {salida.get('requires_physical_return')}")
    print(f"  rejection_reason          : {salida.get('rejection_reason')}")
    if modo == "rag":
        print(f"  answer_grounded           : {salida.get('answer_grounded')}")
        print(f"  sources_used              : {salida.get('sources_used')}")
    print(f"  escalate_to_human         : {salida.get('escalate_to_human')}")
    print(f"  reasoning                 : {salida.get('reasoning')}")

    pasos = salida.get("steps") or []
    if pasos:
        print("\nPasos del proceso:")
        for indice, paso in enumerate(pasos, start=1):
            print(f"  {indice}. {paso}")

    print("\nMensaje entregado al cliente:")
    print(_parrafo(salida.get("customer_response", "")))
    return salida


def ejecutar_todos(motivo: str, hoy: date | None = None, modo: str = "prompt") -> None:
    """Recorre el dataset completo con el mismo motivo, para revisar los casos límite."""
    hoy = hoy or date.today()
    sufijo = " (RAG)" if modo == "rag" else ""
    _titulo(f"BARRIDO DEL DATASET{sufijo} — motivo: {motivo}")
    for pedido in db.cargar_pedidos():
        tracking = pedido["tracking_number"]
        salida = solicitar_devolucion(tracking, motivo, hoy=hoy, modo=modo)
        if "_error" in salida:
            print(f"\n{tracking}  {pedido['status']:<12}  JSON inválido")
            continue
        print(f"\n{tracking}  {pedido['status']:<12}  {pedido['product_category']}")
        print(
            f"  eligible={salida.get('return_eligible')}"
            f"  method={salida.get('return_method')}"
            f"  rejection={salida.get('rejection_reason')}"
            f"  physical={salida.get('requires_physical_return')}"
        )
        if modo == "rag":
            print(
                f"  grounded={salida.get('answer_grounded')}"
                f"  sources={salida.get('sources_used')}"
            )
        print(_parrafo(salida.get("customer_response", "")))


def listar_pedidos() -> None:
    """Muestra los atributos del dataset que deciden la elegibilidad."""
    _titulo("PEDIDOS Y ATRIBUTOS RELEVANTES PARA DEVOLUCIÓN")
    print(f"  {'TRACKING':<15} {'ESTADO':<12} {'CATEGORÍA':<18} {'PERECE':<7} {'HIGIENE':<8} ENTREGA")
    for pedido in db.cargar_pedidos():
        print(
            f"  {pedido['tracking_number']:<15}"
            f" {pedido['status']:<12}"
            f" {pedido['product_category']:<18}"
            f" {str(pedido['is_perishable']):<7}"
            f" {str(pedido['is_hygiene_item']):<8}"
            f" {pedido['delivered_date'] or '—'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking", help="Número de seguimiento del pedido a devolver")
    parser.add_argument(
        "--motivo",
        choices=MOTIVOS,
        default="cambio_de_opinion",
        help="Motivo que declara el cliente (por defecto: cambio_de_opinion)",
    )
    parser.add_argument(
        "--modo",
        choices=("prompt", "rag"),
        default="prompt",
        help="prompt = política escrita en el prompt (Taller 1); "
        "rag = política recuperada de la base de conocimiento (Taller 2)",
    )
    parser.add_argument("--consulta", help="Texto libre del cliente")
    parser.add_argument(
        "--fecha",
        help="Fecha de referencia YYYY-MM-DD para calcular las ventanas (por defecto: hoy)",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Ejecuta la solicitud contra todos los pedidos del dataset",
    )
    parser.add_argument("--listar", action="store_true", help="Lista los pedidos y sus atributos")
    args = parser.parse_args()

    hoy = date.fromisoformat(args.fecha) if args.fecha else date.today()

    if args.listar:
        listar_pedidos()
        return

    if not (args.todos or args.tracking):
        parser.error("indica un número de seguimiento con --tracking, o usa --todos / --listar")

    if args.modo == "rag":
        base_conocimiento.verificar_indice()

    if args.todos:
        ejecutar_todos(args.motivo, hoy, args.modo)
        return

    ejecutar(args.tracking, args.motivo, args.consulta, hoy, args.modo)


if __name__ == "__main__":
    main()
