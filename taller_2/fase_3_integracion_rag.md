### Integración y Ejecución del Código (RAG con LangChain)

Esta fase lleva a código la propuesta de las fases 1 y 2: el agente del Taller 1
(`src/main.py`) ahora complementa el registro del pedido con fragmentos recuperados
de una base de conocimiento vectorial.

#### Arquitectura implementada

```
                    ┌────────────────── Indexación (offline) ──────────────────┐
data/conocimiento/  │ Extracción ─► Chunking ─► Embeddings bge-m3 ─► ChromaDB   │
 ├ manual_politicas │ (md / pdf)    recursivo    (Ollama)            (upsert)   │
 ├ catalogo (json)  │ (json)        1 registro = 1 chunk                        │
 └ faq (json)       └──────────────────────────────────────────────────────────┘

                    ┌────────────────── Consulta (online) ─────────────────────┐
consulta cliente ──►│ ¿trae tracking? ─► db.buscar_pedido ─► <datos_pedido>     │
                    │ retriever top-k + filtro por SKU ─► <contexto_recuperado> │
                    │ PROMPT_RAG ─► LLM del Taller 1 (qwen2.5 vía Ollama) ─► JSON│
                    └──────────────────────────────────────────────────────────┘
```

| Pieza | Decisión de la propuesta | Implementación |
| :--- | :--- | :--- |
| Modelo de embeddings (Fase 1) | `bge-m3` open-source / `text-embedding-3-small` | `OllamaEmbeddings("bge-m3")`; se cambia a OpenAI con `EMBEDDINGS_PROVIDER=openai` |
| Base vectorial (Fase 1) | ChromaDB para prototipo; Pinecone/Weaviate en producción | `langchain_chroma.Chroma` persistente, similitud coseno |
| Documentos (Fase 2) | Manual de políticas, catálogo, FAQ | `data/conocimiento/` (Markdown + 2 JSON) |
| Chunking narrativo (Fase 2) | Recursivo, 500 tokens, overlap 50 | `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` |
| Chunking estructurado (Fase 2) | 1 registro = 1 chunk con metadatos | 18 productos y 13 FAQ, con `sku`, `categoria`, `stock` como metadatos |
| Filtros por metadatos (Fase 1) | Aislar por producto o categoría | La ficha del producto del pedido se recupera con `filter={"sku": ...}` |
| Generación | LLM del Taller 1 | `ChatOpenAI` apuntando al mismo endpoint de `src/llm.py`, en modo JSON |

#### Archivos nuevos o modificados

| Archivo | Rol |
| :--- | :--- |
| `src/base_conocimiento.py` | Pipeline de indexación (extracción, chunking, embeddings, upsert). |
| `src/rag.py` | Retriever y cadena LCEL que une pedido + contexto + prompt + LLM. |
| `src/prompts_rag.py` | Prompt del agente con RAG (reglas de *grounding*, citas y 2 ejemplos few-shot). |
| `src/main.py` | Nuevo modo `--modo rag` y comando `--indexar`; los modos del Taller 1 no cambian. |
| `data/conocimiento/*` | Base de conocimiento de EcoMarket. |

#### Ejecución

```bash
pip install -r requirements.txt
ollama pull qwen2.5:3b && ollama pull bge-m3      # o: docker compose up -d ollama model-loader

python3 -m src.main --indexar                       # 42 chunks: 11 políticas, 18 catálogo, 13 FAQ
python -m src.base_conocimiento --buscar "¿puedo devolver un jabón?"   # prueba del retriever, sin LLM

# Preguntas abiertas, sin pedido
python3 -m src.main --modo rag --consulta "¿Puedo devolver un jabón que ya abrí porque no me gustó el olor?"
python3 -m src.main --modo rag --consulta "¿Venden bicicletas eléctricas?"

# Preguntas sobre un pedido (el tracking se pasa con --tracking o se detecta en el texto)
python3 -m src.main --modo rag --tracking ECO-2024-0004 --consulta "¿Me devuelven el costo del envío por el retraso?"
python3 -m src.main --modo rag --consulta "Mi pedido ECO-2024-0008 dejó de funcionar a los 3 meses, ¿qué hago?"

# Con Docker
docker compose run --rm app --indexar
docker compose run --rm app --modo rag --consulta "¿Cuánto cuesta el envío a Cali?"
```

Si el índice no existe, el modo `rag` lo construye automáticamente la primera vez.

#### Resultados observados (qwen2.5:3b + bge-m3)

| Consulta | Fragmentos recuperados | Resultado |
| :--- | :--- | :--- |
| Devolver un jabón abierto por el olor | FAQ higiene, política 4.1 Retracto, FAQ producto abierto, ficha del jabón | Rechaza la devolución por ser de higiene y ofrece la garantía si llegó dañado. |
| ECO-2024-0004: ¿devuelven el envío por el retraso? | Ficha del producto (filtro SKU), política 2. Retrasos | Confirma el reembolso del envío (retraso > 5 días hábiles), con cita `[2]`. |
| ECO-2024-0008: el panel solar dejó de funcionar a los 3 meses | Ficha del panel (filtro SKU), política 5. Garantía de tecnología | Informa la garantía del fabricante de 12 meses (reparación o reemplazo). |
| ¿Venden bicicletas eléctricas? | Productos de tecnología no relacionados | `answer_grounded: false`, escala a un asesor y no inventa productos. |

El caso del panel solar muestra por qué la consulta de búsqueda se enriquece con el
producto y la categoría del pedido: sin ese ajuste, la sección 5 del manual quedaba
en el puesto 8 del ranking y el modelo respondía con la garantía genérica de 30 días.

Las limitaciones y suposiciones de esta implementación están documentadas en el
[README](../README.md#limitaciones-y-suposiciones-del-taller-2).
