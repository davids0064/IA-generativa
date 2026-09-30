# Fase 3 — Integración y Ejecución del Código

Navegación: [`README general`](../../README.md) · [`Taller 2`](../README.md) · [`Fase 1`](./fase_1_seleccion_componentes.md) · [`Fase 2`](./fase_2_creacion_base_conocimiento.md) · **Fase 3** · [`Pruebas`](./resultados_pruebas.md)

---

### Integración y Ejecución del Código (RAG con LangChain)

Esta fase lleva a código la propuesta de las fases 1 y 2: el agente del Taller 1
(`src/main.py`) ahora complementa el registro del pedido con fragmentos recuperados
de una base de conocimiento vectorial.

#### Arquitectura implementada

```
 INDEXACIÓN — una sola vez (servicio indexer / uv run python -m src.base_conocimiento)

 data/conocimiento/ ─► Extracción ─► Chunking ─► Embeddings bge-m3 ─► upsert ─┐
  (manual md/pdf,       (md, pdf,     (recursivo /   (Ollama)                  │
   catálogo, FAQ)        json)         1 registro)                             ▼
                                                              ┌─────────────────────────┐
                                                              │   Servidor ChromaDB     │
                                                              │ (volumen chroma-data)   │
                                                              └─────────────────────────┘
                                                                           ▲
 CONSULTA — en cada ejecución (main.py / main_devolucion.py)               │
                                                                           │
 consulta ─► ¿tracking? ─► db.buscar_pedido ─► <datos_pedido>              │
         └─► retriever top-k + filtros por metadatos (sku, sección) ───────┘
                 ─► <contexto_recuperado>
         ─► PROMPT_RAG ─► LLM del Taller 1 (qwen2.5 vía Ollama) ─► JSON con citas
```

| Pieza | Decisión de la propuesta | Implementación |
| :--- | :--- | :--- |
| Modelo de embeddings (Fase 1) | `bge-m3` open-source / `text-embedding-3-small` | `OllamaEmbeddings("bge-m3")`; se cambia a OpenAI con `EMBEDDINGS_PROVIDER=openai` |
| Base vectorial (Fase 1) | ChromaDB para prototipo; Weaviate en producción | Servidor ChromaDB (`chromadb/chroma:1.5.9`) al que se conecta `langchain_chroma.Chroma` vía `HttpClient`; similitud coseno. Sin `CHROMA_HOST`, modo embebido |
| Documentos (Fase 2) | Manual de políticas, catálogo, FAQ | `data/conocimiento/` (Markdown + 2 JSON) |
| Chunking narrativo (Fase 2) | Recursivo, 500 tokens, overlap 50 | `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` |
| Chunking estructurado (Fase 2) | 1 registro = 1 chunk con metadatos | 18 productos y 13 FAQ, con `sku`, `categoria`, `stock` como metadatos |
| Filtros por metadatos (Fase 1) | Aislar por producto o categoría | La ficha del producto del pedido se recupera con `filter={"sku": ...}` |
| Generación | LLM del Taller 1 | `ChatOpenAI` apuntando al mismo endpoint de `src/llm.py`, en modo JSON |

#### Archivos nuevos o modificados

| Archivo | Rol |
| :--- | :--- |
| `src/base_conocimiento.py` | Pipeline de indexación (extracción, chunking, embeddings, upsert), ejecutado una sola vez; conexión compartida a ChromaDB (un cliente por proceso). |
| `src/evaluacion_recuperacion.py` | Evaluación de la recuperación sin LLM (hit@k, MRR) para comparar modelos de embeddings y estrategias de chunking (Fases 1 y 2). |
| `src/rag.py` | Retriever y cadenas LCEL que unen pedido + contexto + prompt + LLM (consultas generales y devoluciones). |
| `src/prompts_rag.py` | Prompt del agente con RAG (reglas de *grounding*, citas y 2 ejemplos few-shot). |
| `src/prompts_devolucion_rag.py` | Prompt de devoluciones sin la política escrita: conserva el procedimiento (motivo, árbol de decisión, guion por estado) y toma ventanas, exclusiones y plazos de los fragmentos citados. |
| `src/main.py` | Nuevo modo `--modo rag`, que solo consulta la base vectorial; los modos del Taller 1 no cambian. |
| `src/main_devolucion.py` | Nuevo `--modo rag` (también con `--todos`); `--modo prompt`, el del Taller 1, sigue siendo el predeterminado. |
| `data/conocimiento/*` | Base de conocimiento de EcoMarket. |

#### Ejecución

```bash
uv sync                                            # entorno .venv (pyproject.toml + uv.lock)
docker compose up -d ollama model-loader chroma    # LLM, embeddings y servidor ChromaDB

# Carga única de la base de conocimiento (42 chunks: 11 políticas, 18 catálogo, 13 FAQ).
# Si la colección ya tiene documentos no vuelve a cargarla; --reindexar la reconstruye.
docker compose run --rm indexer                     # o: uv run python -m src.base_conocimiento
uv run python -m src.base_conocimiento --buscar "¿puedo devolver un jabón?"   # prueba del retriever, sin LLM

# Preguntas abiertas, sin pedido
uv run python -m src.main --modo rag --consulta "¿Puedo devolver un jabón que ya abrí porque no me gustó el olor?"
uv run python -m src.main --modo rag --consulta "¿Venden bicicletas eléctricas?"

# Preguntas sobre un pedido (el tracking se pasa con --tracking o se detecta en el texto)
uv run python -m src.main --modo rag --tracking ECO-2024-0004 --consulta "¿Me devuelven el costo del envío por el retraso?"
uv run python -m src.main --modo rag --consulta "Mi pedido ECO-2024-0008 dejó de funcionar a los 3 meses, ¿qué hago?"

# Devoluciones con la política recuperada del manual
uv run python -m src.main_devolucion --modo rag --tracking ECO-2024-0008 --motivo producto_defectuoso
uv run python -m src.main_devolucion --modo rag --todos --motivo cambio_de_opinion   # barrido del dataset

# Con Docker (la app depende de indexer, que no recarga si la colección ya existe)
docker compose run --rm app --modo rag --consulta "¿Cuánto cuesta el envío a Cali?"
docker compose run --rm --entrypoint python app -m src.main_devolucion --modo rag --tracking ECO-2024-0008
```

Los agentes nunca indexan: si ChromaDB no responde o la colección está vacía, terminan
con un mensaje que indica el comando para levantarla o cargarla.

#### Resultados observados (qwen2.5:3b + bge-m3)

Primera ronda de pruebas, durante el desarrollo. La prueba formal de la entrega, con el
resultado esperado de cada caso, las capturas y el análisis de aciertos y fallos, está en
[`resultados_pruebas.md`](./resultados_pruebas.md).

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
[README](../README.md#limitaciones-y-suposiciones).

---

Continuar con [`Resultados de las pruebas`](./resultados_pruebas.md)
