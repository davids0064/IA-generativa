"""Cadena RAG de EcoMarket construida con LangChain (Taller 2 — Fase 3).

Conecta las piezas del sistema:

    consulta ──► retriever (ChromaDB + bge-m3) ──► contexto numerado ─┐
    tracking ──► db.buscar_pedido (datos transaccionales) ────────────┼─► prompt ─► LLM ─► JSON
                                                                      │
El LLM es el mismo del Taller 1 (`llm.py`): cualquier endpoint compatible con
OpenAI, por defecto Ollama en local.
"""

import os
import re

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_openai import ChatOpenAI

from src import base_conocimiento, db, llm
from src.prompts_rag import PROMPT_RAG

TOP_K = int(os.getenv("RAG_TOP_K", "4"))

# Números de seguimiento con el formato ECO-AAAA-NNNN escritos en la consulta.
PATRON_TRACKING = re.compile(r"\bECO-\d{4}-\d{4}\b", re.IGNORECASE)


def detectar_tracking(consulta: str) -> str | None:
    """Extrae el primer número de seguimiento mencionado en la consulta."""
    coincidencia = PATRON_TRACKING.search(consulta)
    return coincidencia.group(0).upper() if coincidencia else None


def recuperar(consulta: str, sku: str | None = None, k: int = TOP_K) -> list[Document]:
    """Búsqueda semántica en la base de conocimiento.

    Si la consulta está asociada a un pedido, se añade la ficha de su producto
    mediante un filtro por metadatos (`sku`), sin depender de que la similitud
    semántica la encuentre.
    """
    vectorstore = base_conocimiento.obtener_vectorstore()
    documentos = vectorstore.similarity_search(consulta, k=k)
    if sku:
        ficha = vectorstore.similarity_search(consulta, k=1, filter={"sku": sku})
        documentos = ficha + [d for d in documentos if d.metadata.get("sku") != sku]
    return documentos


def _etiqueta(doc: Document) -> str:
    """Describe el origen del fragmento: fuente y sección, SKU o categoría."""
    m = doc.metadata
    detalle = m.get("subseccion") or m.get("seccion") or m.get("sku") or m.get("categoria", "")
    return f"{m['fuente']} · {detalle}" if detalle else m["fuente"]


def formatear_contexto(documentos: list[Document]) -> str:
    """Numera los fragmentos para que el modelo pueda citarlos en `sources_used`."""
    return "\n\n".join(
        f"[{i}] ({_etiqueta(doc)})\n{doc.page_content}" for i, doc in enumerate(documentos, start=1)
    )


def _modelo_chat() -> ChatOpenAI:
    """El LLM del Taller 1 envuelto como componente de LangChain, en modo JSON."""
    return ChatOpenAI(
        base_url=llm.BASE_URL,
        api_key=llm.API_KEY,
        model=llm.MODELO,
        temperature=llm.TEMPERATURA,
    ).bind(response_format={"type": "json_object"})


def construir_cadena() -> Runnable:
    """Cadena LCEL. Entrada: {consulta, tracking}. Salida: documentos, registro y respuesta."""

    def _pedido(entrada: dict) -> dict | None:
        tracking = entrada.get("tracking") or detectar_tracking(entrada["consulta"])
        return db.buscar_pedido(tracking) if tracking else None

    def _documentos(entrada: dict) -> list[Document]:
        pedido = entrada["pedido"]
        if not pedido:
            return recuperar(entrada["consulta"])
        # El cliente rara vez nombra el producto ("dejó de funcionar"); añadirlo
        # a la búsqueda acerca las políticas específicas de su categoría.
        consulta = (
            f"{entrada['consulta']}\n"
            f"Producto: {pedido['product']} (categoría {pedido['product_category']})"
        )
        return recuperar(consulta, sku=pedido["sku"])

    return (
        RunnablePassthrough.assign(pedido=_pedido)
        .assign(
            documentos=_documentos,
            registro_json=lambda x: db.formatear_para_prompt(x["pedido"], campos=db.CAMPOS_PEDIDO),
        )
        .assign(contexto=lambda x: formatear_contexto(x["documentos"]))
        .assign(respuesta=PROMPT_RAG | _modelo_chat() | JsonOutputParser())
    )


def responder(consulta: str, tracking: str | None = None) -> dict:
    """Ejecuta la cadena completa sobre una consulta del cliente."""
    return construir_cadena().invoke({"consulta": consulta, "tracking": tracking})
