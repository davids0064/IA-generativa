# Fase 1 — Selección de Componentes

📎 Navegación: [`README general`](../../README.md) · [`Taller 2`](../README.md) · **Fase 1** · [`Fase 2`](./fase_2_creacion_base_conocimiento.md) · [`Fase 3`](./fase_3_integracion_rag.md) · [`Pruebas`](./resultados_pruebas.md)

---

En un sistema RAG el modelo de lenguaje solo puede responder bien con lo que el
retriever le entrega: si el fragmento con la política correcta no llega al prompt, ni
el mejor LLM acierta (es lo que ocurrió en el
[caso 2 de las pruebas](./resultados_pruebas.md#caso-2--reembolso-del-envío-por-retraso-pedido-eco-2024-0004)).
Por eso el modelo de embeddings y la base vectorial fijan el **techo de calidad** del
agente de EcoMarket. Esta fase elige ambos a partir de las necesidades del caso.

## Contenido

- [0. Requisitos de EcoMarket que guían la elección](#0-requisitos-de-ecomarket-que-guían-la-elección)
- [1. Modelo de embeddings](#1-modelo-de-embeddings)
- [2. Base de datos vectorial](#2-base-de-datos-vectorial)
- [3. Cómo impacta cada componente en la eficacia del RAG](#3-cómo-impacta-cada-componente-en-la-eficacia-del-rag)
- [4. Resumen de la decisión](#4-resumen-de-la-decisión)

---

## 0. Requisitos de EcoMarket que guían la elección

| Requisito | Origen | Implicación técnica |
| :--- | :--- | :--- |
| **Consultas en español coloquial** ("me devuelven la plata", "champú", "anular la compra") | Clientes de Colombia por chat, correo y redes | El modelo de embeddings debe entender sinónimos y registro informal en español, no solo coincidencias de palabras. |
| **Precisión en reglas de negocio** (plazos, exclusiones, garantías) | 80 % de consultas repetitivas: pedidos, devoluciones, productos | La recuperación debe traer la sección exacta del manual; confundir "5 días hábiles" con "30 días" es un error grave. |
| **Búsqueda por identificadores exactos** (SKU `ECO-TEC-078`, categorías) | Catálogo y pedidos | La base vectorial debe filtrar por metadatos y, idealmente, combinar búsqueda semántica con coincidencia exacta (búsqueda híbrida). |
| **Privacidad** de las consultas (pueden incluir nombres, direcciones, números de pedido) | Riesgo ético del Taller 1, Fase 2 | Preferir componentes que puedan ejecutarse en infraestructura propia, sin enviar el texto del cliente a terceros. |
| **Volumen:** miles de consultas diarias con picos (Black Friday); base de conocimiento de decenas a miles de documentos | Enunciado del caso | La escala en número de vectores es modesta; lo crítico es la latencia por consulta y absorber picos de tráfico. |
| **Costo bajo y sin dependencia de un proveedor** | Crecimiento de la empresa | Evitar costos por consulta que crezcan con el tráfico y bloqueos a un único proveedor. |

---

## 1. Modelo de embeddings

### 1.1. Alternativas evaluadas

| Modelo | Tipo | Dimensiones | Contexto máx. | Español | Costo | Ventajas | Desventajas |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- | :--- |
| **`bge-m3`** (BAAI) | Open-source (MIT) | 1024 | 8.192 tokens | Multilingüe nativo (100+ idiomas); entrenado para recuperación multilingüe | Sin costo por token; requiere servidor propio (~1,2 GB en Ollama) | Alta calidad de recuperación en español; contexto largo; además de vectores densos ofrece vectores dispersos (léxicos), útiles para búsqueda híbrida | Modelo grande (~570 M parámetros): más lento en CPU que los modelos pequeños; hay que operarlo |
| `text-embedding-3-small` (OpenAI) | Propietario (API) | 1536 | 8.191 tokens | Muy bueno | USD 0,02 por millón de tokens | Sin infraestructura; escala automáticamente; calidad alta | El texto del cliente sale a un tercero; dependencia del proveedor y de la red; latencia de red en cada consulta |
| `text-embedding-3-large` (OpenAI) | Propietario (API) | 3072 | 8.191 tokens | Excelente | USD 0,13 por millón de tokens | La mayor calidad de la familia | Mismas desventajas que el anterior; vectores 2× más grandes (más almacenamiento y latencia) |
| `multilingual-e5-large` (Microsoft) | Open-source (MIT) | 1024 | 512 tokens | Bueno | Sin costo por token | Buen desempeño multilingüe | Contexto de 512 tokens: trunca chunks largos; exige prefijos `query:` / `passage:` |
| `nomic-embed-text-v2-moe` (Nomic) | Open-source (Apache 2.0) | 768 | 512 tokens | Bueno | Sin costo por token | Ligero y rápido; dimensiones reducibles | Contexto de 512 tokens; menor precisión que `bge-m3` en nuestra evaluación (abajo) |

### 1.2. Evidencia propia: evaluación de recuperación en español

Las cifras publicadas (por ejemplo, las tablas de MTEB) son un buen punto de partida,
pero se miden con otros textos. Para decidir con datos de EcoMarket se construyó una
evaluación reproducible, [`src/evaluacion_recuperacion.py`](../src/evaluacion_recuperacion.py):
20 consultas redactadas como las escribiría un cliente, evitando repetir las palabras
de los documentos, cada una con la frase del documento que la responde. Se mide si esa
frase aparece en el primer fragmento recuperado (hit@1), entre los 4 que recibe el LLM
(hit@4), y el rango recíproco medio (MRR@4).

```bash
uv run python -m src.evaluacion_recuperacion --modelos bge-m3 nomic-embed-text-v2-moe
```

| Modelo | hit@1 | hit@4 | MRR@4 |
| :--- | ---: | ---: | ---: |
| **`bge-m3`** | **80 %** | **100 %** | **0,89** |
| `nomic-embed-text-v2-moe` (con sus prefijos `search_query:` / `search_document:`) | 65 % | 95 % | 0,77 |

*Chunking estructurado de la Fase 2 en ambos casos; ejecución del 2026-09-29.*

`bge-m3` pone el fragmento correcto en primer lugar en 4 de cada 5 consultas y nunca lo
deja fuera de los 4 que ve el LLM. `nomic-embed-text-v2-moe` falla, por ejemplo, en
"Las fresas llegaron podridas, ¿qué hago?", donde no relaciona "podridas" con la
garantía de perecederos. Con 20 consultas la muestra es pequeña, pero la diferencia es
consistente en las tres métricas. Los modelos de OpenAI no se evaluaron porque
requieren una clave de pago; el script los puede incorporar sin cambios de diseño.

### 1.3. Análisis de costo

El costo de los embeddings es **marginal frente al del LLM** con cualquiera de las opciones:

- **Indexación:** la base de conocimiento completa ocupa unos 3.500 tokens (42 chunks).
  Con `text-embedding-3-small` costaría menos de una milésima de dólar indexarla, y
  reindexarla a diario sería igual de barato.
- **Consultas:** con 5.000 consultas diarias de unos 30 tokens (150.000 tokens/día),
  `text-embedding-3-small` costaría alrededor de USD 0,003 al día, unos USD 1 al año.
- **`bge-m3` propio:** no tiene costo por token; su costo es el servidor. En esta
  implementación comparte el contenedor de Ollama con el LLM, así que el costo
  incremental es de ~1,2 GB de disco y memoria.

Por lo tanto, el costo **no es el factor decisivo**. Deciden la calidad en español, la
privacidad y la independencia del proveedor.

### 1.4. Elección: `bge-m3`

1. **Rendimiento en español:** es el mejor de las alternativas evaluadas con consultas
   reales del dominio (sección 1.2), y su entrenamiento multilingüe cubre el registro
   coloquial ("plata", "champú", "anular").
2. **Privacidad:** se ejecuta en la infraestructura de EcoMarket, de modo que el texto
   del cliente no sale a un tercero. Es coherente con la mitigación de privacidad del
   Taller 1 (Fase 2).
3. **Contexto de 8.192 tokens:** ningún chunk se trunca, a diferencia de los modelos de
   512 tokens, que obligarían a partir secciones del manual.
4. **Camino a búsqueda híbrida:** además de vectores densos, `bge-m3` produce vectores
   dispersos (léxicos), útiles para coincidencias exactas de SKU y nombres de producto.
   Ollama solo expone los densos; aprovechar los dispersos es una mejora futura.
5. **Sin costo por token ni dependencia de proveedor**, con una salida sencilla si fuera
   necesaria: cambiar a `text-embedding-3-small` es una variable de entorno
   (`EMBEDDINGS_PROVIDER=openai`) más una reindexación.

**Desventajas asumidas:** en CPU es más lento que un modelo pequeño (la indexación de
los 42 chunks toma entre 10 y 20 s en el portátil de pruebas, y cada consulta suma el
cálculo de su vector), y el equipo debe operar el servidor de modelos. **Alternativa recomendada** si EcoMarket no quiere
operar modelos: `text-embedding-3-small` bajo un contrato empresarial sin retención de
datos.

---

## 2. Base de datos vectorial

### 2.1. Alternativas evaluadas

| Base vectorial | Modelo de despliegue | Filtros por metadatos | Búsqueda híbrida (semántica + exacta) | Escalabilidad | Costo | Ventajas | Desventajas |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| **ChromaDB** | Open-source; embebida o servidor (Docker) | Sí | Parcial (filtro por texto contenido, sin ranking BM25) | Un nodo en la versión open-source; alta disponibilidad solo en su nube | Gratis (open-source) | Mínima fricción: `pip`/Docker, integración nativa con LangChain, ideal para prototipar | Sin réplicas ni multi-tenant en open-source; híbrida limitada |
| **Weaviate** | Open-source autohospedado o nube gestionada | Sí | **Nativa** (BM25 + vectores, con peso ajustable) | Horizontal, con réplicas y multi-tenancy | Gratis autohospedado; pago en su nube | Híbrida nativa (clave para SKU y nombres de producto), control total de los datos | Más compleja de operar (esquema, recursos de memoria) |
| **Pinecone** | Solo servicio gestionado (serverless) | Sí | Sí (vectores densos + dispersos) | Automática, sin administrar servidores | Pago por uso y almacenamiento | Cero operación, escala sola ante picos, rápida salida a producción | Datos en un tercero; dependencia del proveedor; costo que crece con el tráfico |
| **Qdrant** | Open-source autohospedado o nube | Sí (muy expresivos) | Sí (vectores dispersos) | Horizontal, con réplicas | Gratis autohospedado | Alto rendimiento, filtros potentes | Híbrida menos directa que Weaviate |
| **pgvector** (PostgreSQL) | Extensión de una base relacional | Sí (SQL) | Con búsqueda de texto de PostgreSQL | La de PostgreSQL | Gratis | Reutiliza la base de datos transaccional existente | Rendimiento vectorial inferior a motores dedicados a gran escala |

### 2.2. Qué necesita realmente EcoMarket

- **Filtros por metadatos:** imprescindibles. La implementación los usa para traer la
  ficha exacta del producto del pedido (`sku`) y las secciones del manual que deciden una
  devolución (`subseccion`), sin depender del ranking semántico. Todas las opciones los
  soportan.
- **Búsqueda híbrida:** muy deseable. Un cliente que escribe "ECO-TEC-078" o "panel de
  60W" necesita coincidencia exacta, no solo similitud. Aquí se diferencian Weaviate,
  Pinecone y Qdrant de ChromaDB.
- **Escala:** la base de conocimiento es pequeña (42 chunks hoy; unos miles aunque el
  catálogo crezca a miles de productos), y miles de consultas diarias equivalen a menos
  de una consulta por segundo en promedio. **Ningún candidato tiene problemas de volumen**;
  la escalabilidad relevante es la operativa: réplicas para disponibilidad y absorber
  picos de campaña.
- **Privacidad y control:** favorece las opciones autohospedadas (ChromaDB, Weaviate, Qdrant).

### 2.3. Elección: ChromaDB para el prototipo, Weaviate para producción

| Etapa | Base vectorial | Justificación |
| :--- | :--- | :--- |
| **Prototipo (implementado)** | **ChromaDB 1.5.9 en modo servidor** (contenedor Docker, volumen persistente) | Cero costo y mínima operación; la misma interfaz `VectorStore` de LangChain que las demás; soporta los filtros por metadatos que usa el agente; la carga se hace una sola vez y los agentes solo se conectan. A la escala actual de EcoMarket sería suficiente incluso para una primera salida a producción. |
| **Producción a escala** | **Weaviate autohospedado** | Búsqueda híbrida nativa (BM25 + vectores) para SKU y nombres de producto; réplicas y multi-tenancy para disponibilidad en picos; datos dentro de la infraestructura de EcoMarket, coherente con la mitigación de privacidad del Taller 1. |
| Alternativa | Pinecone | Si EcoMarket no tiene equipo para operar infraestructura: escalado automático y cero mantenimiento, a cambio de dependencia del proveedor y de un contrato que garantice el tratamiento de los datos. |

**Costo de la migración:** el código accede a la base solo a través de
`obtener_vectorstore()` en [`src/base_conocimiento.py`](../src/base_conocimiento.py).
Pasar a Weaviate implica cambiar esa función y reindexar; el pipeline de ingesta, el
retriever y los prompts no cambian.

---

## 3. Cómo impacta cada componente en la eficacia del RAG

| Decisión | Efecto en el sistema | Evidencia en este proyecto |
| :--- | :--- | :--- |
| Calidad del modelo de embeddings | Fija el techo de *recall*: si la política correcta no queda entre los k fragmentos, el LLM no puede aplicarla (o peor, aplica otra). | `bge-m3` sube el hit@1 de 65 % a 80 % frente a la alternativa (sección 1.2). En el caso 2 de las pruebas, la política de retrasos no se recuperó y el agente no pudo responder. |
| Contexto máximo del modelo | Limita el tamaño de los chunks: un modelo de 512 tokens obligaría a partir secciones del manual y separar una regla de sus excepciones. | Con `bge-m3` (8.192 tokens) cada sección del manual es un solo chunk (Fase 2). |
| Dimensiones del vector | Más dimensiones implican más almacenamiento y latencia de búsqueda, con mejoras marginales de calidad. | 1024 dimensiones × 42 chunks es trivial; a millones de vectores pesaría más. |
| Mismo modelo para indexar y consultar | Vectores de modelos distintos no son comparables: cambiar de modelo exige reindexar. | Documentado en la puesta en marcha (`--reindexar`). |
| Filtros por metadatos de la base vectorial | Permiten garantizar que las reglas críticas lleguen al prompt, sin depender de la similitud. | Con filtros, las secciones que deciden una devolución llegaron al modelo en el 100 % de los casos de prueba (casos 3 y 4). |
| Búsqueda híbrida | Recupera identificadores exactos (SKU) que la similitud semántica confunde. | No disponible en ChromaDB; motiva la elección de Weaviate para producción. |
| Métrica de distancia (coseno) | Compara la orientación de los vectores, independiente de su norma; es la métrica con la que se entrenan estos modelos. | Configurada en la colección (`hnsw:space: cosine`). |

---

## 4. Resumen de la decisión

| Componente | Elección | Criterio decisivo | Alternativa |
| :--- | :--- | :--- | :--- |
| Modelo de embeddings | **`bge-m3`** (open-source, vía Ollama) | Mejor recuperación en español medida sobre datos de EcoMarket, privacidad, contexto de 8K tokens | `text-embedding-3-small` si no se quiere operar modelos |
| Base vectorial (prototipo) | **ChromaDB** en modo servidor | Costo cero, integración directa, filtros por metadatos | — |
| Base vectorial (producción) | **Weaviate** autohospedado | Búsqueda híbrida nativa, réplicas, control de los datos | Pinecone si no hay equipo de operación |

---

📎 Continuar con [`Fase 2 — Creación de la Base de Conocimiento`](./fase_2_creacion_base_conocimiento.md)
