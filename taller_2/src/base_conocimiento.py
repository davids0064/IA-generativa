"""Base de conocimiento de EcoMarket (Taller 2 — Fases 1 y 2).

Implementa el pipeline de indexación definido en
`taller_2/fase_2_creacion_base_conocimiento.md`:

  1. Extracción   -> lectura del manual de políticas (PDF o Markdown), del
                     catálogo de productos (JSON) y de las FAQ (JSON).
  2. Segmentación -> chunking recursivo (500 tokens, overlap 50) para textos
                     narrativos y chunking por documento (1 registro = 1 chunk)
                     para datos estructurados.
  3. Vectorización-> embeddings con `bge-m3` (open-source, servido por Ollama) o
                     `text-embedding-3-small` (OpenAI), según la Fase 1.
  4. Upsert       -> carga de vector, texto y metadatos en ChromaDB.

La carga se hace una sola vez, con este módulo (o el servicio `indexer` de
Docker Compose). Los agentes (`main.py` y `main_devolucion.py`) solo se
conectan a la base vectorial: nunca indexan.

ChromaDB corre como servidor (servicio `chroma` de Docker Compose) cuando se
define `CHROMA_HOST`; sin esa variable se usa en modo embebido, persistido en
`VECTORSTORE_DIR`.

Ejemplo de uso:
    uv run python -m src.base_conocimiento                 # carga si la colección está vacía
    uv run python -m src.base_conocimiento --reindexar     # reconstruye tras cambiar los documentos
    uv run python -m src.base_conocimiento --buscar "¿puedo devolver un jabón?"
"""

import argparse
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pypdf import PdfReader

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CONOCIMIENTO = RAIZ / "data" / "conocimiento"
RUTA_CATALOGO = RUTA_CONOCIMIENTO / "catalogo_productos.json"
RUTA_FAQ = RUTA_CONOCIMIENTO / "faq.json"

EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "ollama")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "bge-m3")
EMBEDDINGS_BASE_URL = os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:11434")
VECTORSTORE_DIR = Path(os.getenv("VECTORSTORE_DIR", RAIZ / "data" / "vectorstore"))
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLECCION = "ecomarket_conocimiento"

# Parámetros de chunking de la Fase 2, expresados en tokens.
CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50


def _contar_tokens(texto: str) -> int:
    """Aproxima el número de tokens (≈ 4 caracteres por token en español).

    Evita depender del tokenizador exacto de `bge-m3`; ver suposiciones en el
    README.
    """
    return math.ceil(len(texto) / 4)


# ---------------------------------------------------------------------------
# 1. Extracción
# ---------------------------------------------------------------------------


def cargar_politicas() -> list[Document]:
    """Carga los manuales narrativos (PDF o Markdown) de la carpeta de conocimiento."""
    documentos = []
    for ruta in sorted(RUTA_CONOCIMIENTO.iterdir()):
        metadatos = {"fuente": "politicas", "documento": ruta.name}
        if ruta.suffix == ".pdf":
            texto = "\n".join(pagina.extract_text() for pagina in PdfReader(ruta).pages)
        elif ruta.suffix == ".md":
            texto = ruta.read_text(encoding="utf-8")
        else:
            continue
        documentos.append(Document(page_content=texto, metadata=metadatos))
    return documentos


def cargar_catalogo() -> list[Document]:
    """Un producto = un chunk, con sus atributos como metadatos filtrables."""
    productos = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))
    documentos = []
    for p in productos:
        disponibilidad = f"{p['stock']} unidades" if p["stock"] else "agotado"
        precio = f"{p['price_cop']:,}".replace(",", ".")
        texto = (
            f"Producto: {p['name']} (SKU {p['sku']})\n"
            f"Categoría: {p['category']}\n"
            f"Precio: ${precio} COP\n"
            f"Disponibilidad: {disponibilidad}\n"
            f"Perecedero: {'sí' if p['is_perishable'] else 'no'} | "
            f"Higiene personal: {'sí' if p['is_hygiene_item'] else 'no'}\n"
            f"Certificaciones: {', '.join(p['certifications'])}\n"
            f"Descripción: {p['description']}"
        )
        documentos.append(
            Document(
                page_content=texto,
                id=f"catalogo-{p['sku']}",
                metadata={
                    "fuente": "catalogo",
                    "documento": RUTA_CATALOGO.name,
                    "sku": p["sku"],
                    "categoria": p["category"],
                    "stock": p["stock"],
                },
            )
        )
    return documentos


def cargar_faq() -> list[Document]:
    """Una pregunta frecuente = un chunk (pregunta + respuesta)."""
    preguntas = json.loads(RUTA_FAQ.read_text(encoding="utf-8"))
    return [
        Document(
            page_content=f"Pregunta frecuente: {f['question']}\nRespuesta: {f['answer']}",
            id=f"faq-{i:03d}",
            metadata={"fuente": "faq", "documento": RUTA_FAQ.name, "categoria": f["category"]},
        )
        for i, f in enumerate(preguntas, start=1)
    ]


# ---------------------------------------------------------------------------
# 2. Segmentación
# ---------------------------------------------------------------------------


def segmentar_politicas(documentos: list[Document]) -> list[Document]:
    """Chunking recursivo de 500 tokens con overlap de 50.

    En Markdown se corta primero por encabezados para que cada chunk conserve
    la sección a la que pertenece (se usa luego para citar la fuente).
    """
    por_encabezado = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "titulo"), ("##", "seccion"), ("###", "subseccion")],
        strip_headers=False,
    )
    recursivo = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_TOKENS,
        chunk_overlap=OVERLAP_TOKENS,
        length_function=_contar_tokens,
    )

    chunks = []
    for doc in documentos:
        if doc.metadata["documento"].endswith(".md"):
            secciones = por_encabezado.split_text(doc.page_content)
            for seccion in secciones:
                seccion.metadata = {**doc.metadata, **seccion.metadata}
        else:
            secciones = [doc]
        chunks.extend(recursivo.split_documents(secciones))

    for i, chunk in enumerate(chunks, start=1):
        chunk.id = f"politicas-{i:03d}"
        # Chroma solo admite metadatos escalares.
        chunk.metadata = {k: v for k, v in chunk.metadata.items() if v is not None}
    return chunks


# ---------------------------------------------------------------------------
# 3. Vectorización y 4. Almacenamiento
# ---------------------------------------------------------------------------


def obtener_embeddings() -> Embeddings:
    """Modelo de embeddings elegido en la Fase 1 (open-source o propietario)."""
    if EMBEDDINGS_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"))

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=EMBEDDINGS_MODEL, base_url=EMBEDDINGS_BASE_URL)


def destino() -> str:
    """Describe dónde vive la base vectorial, para los mensajes al usuario."""
    return f"http://{CHROMA_HOST}:{CHROMA_PORT}" if CHROMA_HOST else str(VECTORSTORE_DIR)


@lru_cache(maxsize=1)
def obtener_vectorstore() -> Chroma:
    """Conexión a la colección de ChromaDB (similitud coseno), una por proceso.

    Se reutiliza en todas las búsquedas: en un barrido de `main_devolucion`
    son decenas de consultas y abrir un cliente por cada una es lo que más
    tiempo consumía fuera del LLM.
    """
    if CHROMA_HOST:
        conexion = {"client": chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)}
    else:
        conexion = {"persist_directory": str(VECTORSTORE_DIR)}
    return Chroma(
        collection_name=COLECCION,
        embedding_function=obtener_embeddings(),
        collection_metadata={"hnsw:space": "cosine"},
        **conexion,
    )


def construir_chunks() -> list[Document]:
    """Ejecuta extracción y segmentación de las tres fuentes."""
    return segmentar_politicas(cargar_politicas()) + cargar_catalogo() + cargar_faq()


def indexar(reiniciar: bool = True) -> int:
    """Pipeline completo. Devuelve el número de chunks indexados.

    Los ids son deterministas, así que volver a indexar hace upsert en lugar
    de duplicar; `reiniciar` además elimina chunks de documentos borrados.
    """
    vectorstore = obtener_vectorstore()
    if reiniciar:
        vectorstore.reset_collection()
    chunks = construir_chunks()
    vectorstore.add_documents(chunks, ids=[c.id for c in chunks])
    return len(chunks)


def esta_indexada() -> bool:
    """Indica si la colección ya tiene documentos."""
    return bool(obtener_vectorstore().get(limit=1)["ids"])


def verificar_indice() -> None:
    """Termina con un mensaje claro si la base vectorial no responde o está vacía.

    Los agentes la llaman al arrancar en modo `rag`, en lugar de indexar por
    su cuenta.
    """
    try:
        vacia = not esta_indexada()
    except Exception as error:  # conexión rechazada, host inexistente, etc.
        raise SystemExit(
            f"No se pudo conectar a la base vectorial en {destino()}: {error}\n"
            "Levanta el servidor con: docker compose up -d chroma"
        ) from error
    if vacia:
        raise SystemExit(
            f"La base de conocimiento en {destino()} está vacía. Cárgala una sola vez con:\n"
            "  uv run python -m src.base_conocimiento      (o: docker compose run --rm indexer)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--reindexar",
        action="store_true",
        help="Borra la colección y vuelve a cargarla (tras cambiar los documentos)",
    )
    parser.add_argument("--buscar", help="Consulta de prueba contra el índice (sin LLM)")
    parser.add_argument("-k", type=int, default=4, help="Número de chunks a recuperar")
    args = parser.parse_args()

    if args.buscar:
        verificar_indice()
        resultados = obtener_vectorstore().similarity_search_with_score(args.buscar, k=args.k)
        for doc, distancia in resultados:
            print(f"\n[{doc.metadata['fuente']}] distancia={distancia:.3f}  {doc.metadata}")
            print(doc.page_content[:300])
        return

    print(f"Embeddings: {EMBEDDINGS_PROVIDER}/{EMBEDDINGS_MODEL}  ->  {destino()}")
    if esta_indexada() and not args.reindexar:
        total = len(obtener_vectorstore().get(include=[])["ids"])
        print(f"La colección '{COLECCION}' ya tiene {total} chunks; no se vuelve a cargar.")
        print("Usa --reindexar si cambiaste los documentos de data/conocimiento.")
        return

    chunks = construir_chunks()
    por_fuente: dict[str, int] = {}
    for c in chunks:
        por_fuente[c.metadata["fuente"]] = por_fuente.get(c.metadata["fuente"], 0) + 1
    print(f"Chunks por fuente: {por_fuente}")
    total = indexar()
    print(f"Indexados {total} chunks en la colección '{COLECCION}'.")


if __name__ == "__main__":
    main()
