# Taller Práctico #2 — Sistema RAG

> **Versión 2 de la solución.** Parte del agente del [Taller 1](../taller_1/README.md) y le
> agrega una base de conocimiento vectorial (políticas, catálogo y FAQ) recuperada con
> LangChain + ChromaDB, para que también responda preguntas abiertas que no están en el
> registro del pedido. Los modos del Taller 1 (`basico`, `mejorado` y el agente de
> devoluciones) siguen disponibles sin cambios.

Volver al [README general](../README.md)

---

## Navegación

| Fase | Descripción | Documento |
| :---: | :--- | :--- |
| **1** | Selección de componentes (embeddings y base vectorial) | [`fase_1_seleccion_componentes.md`](./analisis/fase_1_seleccion_componentes.md) |
| **2** | Creación de la base de conocimiento (ingesta, chunking, indexación) | [`fase_2_creacion_base_conocimiento.md`](./analisis/fase_2_creacion_base_conocimiento.md) |
| **3** | Integración y ejecución del código (LangChain + ChromaDB) | [`fase_3_integracion_rag.md`](./analisis/fase_3_integracion_rag.md) |

- [Estructura de esta versión](#estructura-de-esta-versión)
- [Puesta en marcha](#puesta-en-marcha)
- [Limitaciones y suposiciones](#limitaciones-y-suposiciones)

---

## Estructura de esta versión

```
taller_2/
├── README.md                       # Este archivo
├── analisis/                       # Solución documentada de cada fase
│   ├── fase_1_seleccion_componentes.md
│   ├── fase_2_creacion_base_conocimiento.md
│   └── fase_3_integracion_rag.md
├── data/
│   ├── dataset.json                # Pedidos (misma base simulada del Taller 1)
│   ├── conocimiento/               # Base de conocimiento del RAG
│   │   ├── manual_politicas_garantias.md
│   │   ├── catalogo_productos.json
│   │   └── faq.json
│   └── vectorstore/                # Índice de ChromaDB (generado, no versionado)
├── src/
│   ├── main.py                     # Agente: modos basico/mejorado (Taller 1) + modo rag
│   ├── main_devolucion.py          # Agente de devoluciones (heredado del Taller 1)
│   ├── llm.py · db.py              # Cliente del LLM y acceso a pedidos
│   ├── prompts.py · prompts_devolucion.py
│   ├── base_conocimiento.py        # Pipeline de indexación
│   ├── rag.py                      # Retriever + cadena LangChain
│   └── prompts_rag.py              # Prompt del agente con RAG
├── requirements.txt · .env.example
└── Dockerfile · docker-compose.yml
```

Todos los comandos de este documento se ejecutan **desde la carpeta `taller_2/`**.

---

## Puesta en marcha

```bash
pip install -r requirements.txt
docker compose up -d ollama model-loader    # descarga qwen2.5:3b y bge-m3 (o: ollama pull bge-m3)
python -m src.main --indexar                # construye el índice en data/vectorstore
python -m src.main --modo rag --consulta "¿Puedo devolver un jabón que ya abrí?"
python -m src.main --modo rag --tracking ECO-2024-0004 --consulta "¿Me devuelven el envío por el retraso?"
```

La salida muestra el pedido asociado, los fragmentos recuperados con su fuente y la
respuesta estructurada con las citas usadas (`sources_used`). Más comandos y los
resultados observados están en [`fase_3_integracion_rag.md`](./analisis/fase_3_integracion_rag.md#ejecución).

---

## Limitaciones y suposiciones

La arquitectura propuesta en las fases 1 y 2 está pensada para producción; la
implementación se ejecutó en un portátil, sin GPU dedicada ni presupuesto para
APIs de pago. Estas son las diferencias y las razones.

### Limitaciones de recursos

| Propuesta | Implementado | Razón | Efecto observado |
| :--- | :--- | :--- | :--- |
| LLM de gran capacidad (Taller 1, Fase 1) | `qwen2.5:3b` cuantizado a 4 bits, en Ollama | Corre en CPU/GPU integrada con ~2 GB de RAM y sin costo por token. | Recupera bien pero razona peor: a veces mezcla plazos de dos políticas (por ejemplo, cita los 5 días hábiles del retracto al hablar de la garantía) o agrega frases de un fragmento poco relevante. Con un modelo mayor (`llama3.1:8b`, `gpt-4o-mini`) basta con cambiar `LLM_MODEL` y `LLM_BASE_URL` en `.env`. |
| Pinecone o Weaviate en producción (Fase 1) | ChromaDB local y persistente | No requiere cuenta, servidor ni costo, y usa la misma interfaz `VectorStore` de LangChain. | Sin búsqueda híbrida (SKU exacto + semántica), sin réplicas ni multi-tenant. Migrar implica cambiar solo `obtener_vectorstore()` en `src/base_conocimiento.py`. |
| `bge-m3` servido como API de inferencia | `bge-m3` en el mismo Ollama del LLM | Evita instalar PyTorch (~2 GB) y reutiliza el servidor existente. | Descarga de ~1,2 GB; la indexación de los 42 chunks tarda ~10 s. |
| Ingesta periódica desde los sistemas de EcoMarket | Indexación manual con `--indexar` | No hay acceso a sistemas reales. | El stock del catálogo es una foto fija y no se sincroniza. |

### Suposiciones

1. **Documentos sintéticos.** El manual de políticas, el catálogo (18 productos) y las
   FAQ (13 preguntas) se redactaron para el taller y son coherentes con la política de
   devoluciones del Taller 1. No son documentos reales de EcoMarket.
2. **Manual en Markdown en lugar de PDF.** La Fase 2 menciona un PDF; el pipeline
   admite `.pdf` (con `pypdf`) y `.md`, y se versionó Markdown para que el contenido sea
   legible y editable en el repositorio. Basta con dejar un PDF en `data/conocimiento/`
   y volver a indexar.
3. **Conteo de tokens aproximado.** El chunking de 500 tokens y 50 de overlap usa la
   aproximación de ~4 caracteres por token en español, sin el tokenizador exacto de
   `bge-m3`. Como el manual se corta primero por encabezados, cada sección queda en un
   solo chunk (entre 30 y 240 tokens).
4. **Los pedidos no se vectorizan.** El estado de un pedido cambia a diario y requiere
   coincidencia exacta del número de seguimiento, así que se sigue consultando por
   búsqueda estructurada (`src/db.py`). Esto también evita guardar datos personales
   (nombres, direcciones) en el índice vectorial, en línea con los riesgos de
   privacidad del [Taller 1, Fase 2](../taller_1/analisis/fase_2_evaluacion.md#3-privacidad-de-datos-pii---information-handling).
5. **Consulta de búsqueda enriquecida.** Cuando hay un pedido, la búsqueda añade el
   producto y su categoría a la pregunta del cliente, y la ficha del producto se
   recupera con un filtro por `sku`. Sin esto, preguntas como "dejó de funcionar" no
   recuperan la política específica de la categoría.
6. **Alcance.** El RAG se integró en el agente de `src/main.py`, como pide el
   enunciado. El agente de devoluciones (`src/main_devolucion.py`) conserva la política
   dentro del prompt, y los modos `basico` y `mejorado` del Taller 1 no cambian.
7. **Sin re-ranking, memoria ni evaluación automática.** Se recuperan los 4 chunks más
   similares (`RAG_TOP_K`) sin re-ranker, cada consulta es independiente (sin historial
   de conversación) y la calidad se validó a mano con los casos de
   [`fase_3_integracion_rag.md`](./analisis/fase_3_integracion_rag.md), sin métricas
   como RAGAS.

---

📎 Volver al [README general](../README.md) · Versión anterior: [Taller 1](../taller_1/README.md)
