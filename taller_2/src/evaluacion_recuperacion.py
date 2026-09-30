"""Evaluación de la recuperación (Taller 2 — Fases 1 y 2).

Mide, sin LLM, qué tan bien encuentra el retriever el fragmento que responde
cada consulta, para respaldar con datos dos decisiones de diseño:

  * Fase 1 — modelo de embeddings: compara `bge-m3` con otras alternativas
    servidas por Ollama sobre consultas coloquiales en español.
  * Fase 2 — estrategia de chunking: compara la segmentación estructurada del
    pipeline (encabezados + recursivo para el manual, un registro por chunk
    para catálogo y FAQ) con un chunking ingenuo de tamaño fijo sobre los
    archivos en bruto.

Todo se calcula en memoria (similitud coseno con numpy): no escribe en la
colección de ChromaDB que usan los agentes.

Métricas por combinación modelo × estrategia:
  hit@1  — la primera posición contiene la evidencia.
  hit@k  — alguna de las k primeras la contiene (k = RAG_TOP_K, lo que ve el LLM).
  MRR@k  — media del inverso de la posición de la primera evidencia.
  tokens@k — tokens promedio que ocupan los k fragmentos en el prompt.

Ejemplo de uso:
    uv run python -m src.evaluacion_recuperacion
    uv run python -m src.evaluacion_recuperacion --modelos bge-m3 nomic-embed-text-v2-moe
"""

import argparse
import re

import numpy as np
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import base_conocimiento as bc

# Prefijos que algunos modelos esperan para distinguir consultas de documentos.
# Aplicarlos es necesario para compararlos en igualdad de condiciones.
PREFIJOS = {
    "nomic-embed-text": ("search_query: ", "search_document: "),
    "nomic-embed-text-v2-moe": ("search_query: ", "search_document: "),
}

# Consultas redactadas como las escribiría un cliente, evitando repetir las
# palabras del documento (champú/shampoo, plata/reembolso, anular/cancelar...).
# `evidencia`: fragmentos de texto de la base de conocimiento que responden la
# consulta; basta con que el chunk recuperado contenga uno de ellos.
CONSULTAS = [
    ("Mi pedido lleva una semana de retraso, ¿me regresan lo que pagué por el envío?",
     ["Reembolsa el costo del envío si el retraso supera 5 días hábiles"]),
    ("¿Puedo devolver un champú sólido si ya lo destapé?",
     ["productos de higiene personal y de contacto corporal",
      "¿Por qué no puedo devolver productos de higiene o alimentos?",
      "¿Puedo devolver un producto que ya abrí?"]),
    ("Me arrepentí de comprar las sábanas, ¿cuántos días tengo para regresarlas?",
     ["Ventana: hasta 5 días hábiles desde la entrega"]),
    ("Las fresas llegaron podridas, ¿qué hago?",
     ["sin devolución física, por bioseguridad"]),
    ("El panel solar dejó de cargar después de 4 meses de uso",
     ["garantía del fabricante de 12 meses"]),
    ("¿En cuánto tiempo me devuelven la plata?",
     ["El reembolso se procesa entre 5 y 10 días hábiles", "¿Cuánto tarda el reembolso?"]),
    ("¿Cuánto me cobran por mandar el pedido a Pasto?",
     ["$18.000 COP en el resto del país", "¿Cuánto cuesta el envío?"]),
    ("¿Tardan mucho en llegar los paquetes a Medellín?",
     ["entrega de 2 a 4 días hábiles"]),
    ("Quiero anular una compra que todavía no han despachado",
     ['Un pedido en estado "Procesando" se puede cancelar sin costo']),
    ("¿Cómo me doy de baja de la caja mensual de snacks?",
     ["¿Cómo cancelo mi suscripción?", "Las suscripciones se pueden cancelar en cualquier momento"]),
    ("¿Se puede pagar con Nequi?",
     ["¿Qué medios de pago aceptan?"]),
    ("¿Mandan pedidos a Ecuador?",
     ["¿Hacen envíos internacionales?"]),
    ("¿Tienen algún termo para mantener el café caliente?",
     ["Botella térmica de acero inoxidable 750ml"]),
    ("Busco algo para hacer abono con los residuos de la cocina",
     ["Compostera doméstica 20L"]),
    ("¿Venden algo para reemplazar el papel film?",
     ["Envolturas de cera de abejas"]),
    ("En la página dice entregado pero a mí no me llegó nada",
     ["¿Qué hago si no recibí mi pedido pero aparece como entregado?"]),
    ("¿El chat me puede pedir la clave de mi tarjeta?",
     ["nunca solicita contraseñas"]),
    ("¿A qué hora puedo hablar con una persona?",
     ["de lunes a sábado, de 7:00 a. m. a 8:00 p. m."]),
    ("¿Los productos vienen envueltos en plástico?",
     ["¿Cómo son los empaques de EcoMarket?"]),
    ("Me llegó una camiseta de otra talla, ¿la puedo cambiar?",
     ["pidió una talla equivocada", "no corresponde a lo pedido"]),
]


def _normalizar(texto: str) -> str:
    """Colapsa espacios y saltos de línea para comparar evidencias con chunks."""
    return re.sub(r"\s+", " ", texto).strip().lower()


def chunks_estructurados() -> list[Document]:
    """Los mismos chunks que carga el pipeline (Fase 2)."""
    return bc.construir_chunks()


def chunks_tamano_fijo() -> list[Document]:
    """Línea base ingenua: archivos en bruto cortados cada 500 tokens (overlap 50).

    Sin encabezados, sin separar registros y con la sintaxis JSON incluida, que
    es lo que se obtiene si se omite el diseño de la Fase 2.
    """
    divisor = RecursiveCharacterTextSplitter(
        chunk_size=bc.CHUNK_TOKENS,
        chunk_overlap=bc.OVERLAP_TOKENS,
        length_function=bc._contar_tokens,
    )
    chunks = []
    for ruta in sorted(bc.RUTA_CONOCIMIENTO.iterdir()):
        if ruta.suffix in (".md", ".json"):
            texto = ruta.read_text(encoding="utf-8")
            chunks.extend(divisor.create_documents([texto], metadatas=[{"documento": ruta.name}]))
    return chunks


ESTRATEGIAS = {
    "estructurada": chunks_estructurados,
    "tamaño fijo": chunks_tamano_fijo,
}


def evaluar(modelo: str, chunks: list[Document], k: int) -> dict:
    """Calcula hit@1, hit@k, MRR@k y tokens@k de un modelo sobre un conjunto de chunks."""
    prefijo_consulta, prefijo_doc = PREFIJOS.get(modelo, ("", ""))
    embeddings = OllamaEmbeddings(model=modelo, base_url=bc.EMBEDDINGS_BASE_URL)

    matriz_docs = np.array(embeddings.embed_documents([prefijo_doc + c.page_content for c in chunks]))
    matriz_consultas = np.array(
        embeddings.embed_documents([prefijo_consulta + consulta for consulta, _ in CONSULTAS])
    )
    matriz_docs /= np.linalg.norm(matriz_docs, axis=1, keepdims=True)
    matriz_consultas /= np.linalg.norm(matriz_consultas, axis=1, keepdims=True)
    similitudes = matriz_consultas @ matriz_docs.T

    textos = [_normalizar(c.page_content) for c in chunks]
    hit1 = hitk = rr = tokens = 0.0
    fallos = []
    for i, (consulta, evidencias) in enumerate(CONSULTAS):
        ranking = np.argsort(-similitudes[i])[:k]
        evidencias = [_normalizar(e) for e in evidencias]
        posicion = next(
            (p for p, idx in enumerate(ranking, start=1) if any(e in textos[idx] for e in evidencias)),
            None,
        )
        tokens += sum(bc._contar_tokens(chunks[idx].page_content) for idx in ranking)
        if posicion:
            hitk += 1
            rr += 1 / posicion
            hit1 += posicion == 1
        else:
            fallos.append(consulta)

    n = len(CONSULTAS)
    return {
        "hit@1": hit1 / n,
        f"hit@{k}": hitk / n,
        f"MRR@{k}": rr / n,
        f"tokens@{k}": tokens / n,
        "chunks": len(chunks),
        "fallos": fallos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--modelos",
        nargs="+",
        default=[bc.EMBEDDINGS_MODEL],
        help="Modelos de embeddings de Ollama a comparar (por defecto: EMBEDDINGS_MODEL)",
    )
    parser.add_argument("-k", type=int, default=4, help="Fragmentos que recibe el LLM (RAG_TOP_K)")
    args = parser.parse_args()

    chunks = {nombre: construir() for nombre, construir in ESTRATEGIAS.items()}
    print(f"{len(CONSULTAS)} consultas · k = {args.k} · Ollama en {bc.EMBEDDINGS_BASE_URL}\n")
    print(f"| Modelo | Chunking | Chunks | hit@1 | hit@{args.k} | MRR@{args.k} | tokens@{args.k} |")
    print("| :--- | :--- | ---: | ---: | ---: | ---: | ---: |")
    detalle = []
    for modelo in args.modelos:
        for estrategia, lista in chunks.items():
            r = evaluar(modelo, lista, args.k)
            print(
                f"| `{modelo}` | {estrategia} | {r['chunks']} | {r['hit@1']:.0%} | "
                f"{r[f'hit@{args.k}']:.0%} | {r[f'MRR@{args.k}']:.2f} | {r[f'tokens@{args.k}']:.0f} |"
            )
            detalle.append((modelo, estrategia, r["fallos"]))

    print("\nConsultas sin evidencia en el top-k:")
    for modelo, estrategia, fallos in detalle:
        print(f"  {modelo} · {estrategia}: {len(fallos)}")
        for consulta in fallos:
            print(f"    - {consulta}")


if __name__ == "__main__":
    main()
