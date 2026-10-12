"""Chat de consola con el agente de devoluciones (Proyecto Final).

Muestra, en cada turno, las herramientas que decidió usar el agente, sus
argumentos y el resultado, seguidos de la respuesta al cliente. Sirve para
probar el agente sin la interfaz web.

Ejemplos de uso:
    uv run python -m src.main_agente
    uv run python -m src.main_agente --modelo qwen2.5:3b
    uv run python -m src.main_agente -m "Quiero devolver ECO-2024-0015, no me gustó" -m "Sí, confirmo"
"""

import argparse
import json
import textwrap
import uuid

from src import base_conocimiento
from src.agente.agente import AGENT_MODEL, AgenteDevoluciones
from src.agente.reglas import fecha_referencia

ANCHO = 78


def _mostrar(respuesta) -> None:
    for paso in respuesta.pasos:
        argumentos = json.dumps(paso.argumentos, ensure_ascii=False)
        detalle = paso.resultado.get("error_code") or ""
        if "eligible" in paso.resultado:
            detalle = f"eligible={paso.resultado['eligible']} {detalle}".strip()
        if paso.resultado.get("rma"):
            detalle = f"{paso.resultado['rma']} {detalle}".strip()
        print(f"  ▸ {paso.nombre}({argumentos}) → {paso.status} {detalle}".rstrip())
    print(textwrap.fill(respuesta.texto, width=ANCHO, initial_indent="Eco: ", subsequent_indent="     "))
    for etiqueta in respuesta.etiquetas:
        print(f"     📄 Etiqueta: {etiqueta}")
    print(f"     ({respuesta.latencia_ms / 1000:.1f} s · traza {respuesta.trace_id})\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", default=AGENT_MODEL, help=f"Modelo del agente (por defecto {AGENT_MODEL})")
    parser.add_argument(
        "-m", "--mensaje", action="append",
        help="Mensaje del cliente; se puede repetir para simular una conversación sin modo interactivo",
    )
    args = parser.parse_args()

    try:
        disponible = base_conocimiento.esta_indexada()
    except Exception:  # noqa: BLE001 — ChromaDB caído: el agente funciona igual sin el RAG
        disponible = False
    if not disponible:
        print("Aviso: la base de conocimiento no está disponible; las preguntas de políticas "
              "responderán con un error controlado.\n")

    agente = AgenteDevoluciones(modelo=args.modelo)
    hilo = uuid.uuid4().hex[:8]
    print(f"Agente EcoMarket · modelo {args.modelo} · fecha de referencia {fecha_referencia()} · "
          f"conversación {hilo}\n")

    if args.mensaje:
        for mensaje in args.mensaje:
            print(f"Cliente: {mensaje}")
            _mostrar(agente.responder(mensaje, hilo))
        return

    print("Escribe tu mensaje (o 'salir').\n")
    while True:
        try:
            mensaje = input("Cliente: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if mensaje.lower() in ("salir", "exit", "quit"):
            break
        _mostrar(agente.responder(mensaje, hilo))


if __name__ == "__main__":
    main()
