# Fase 1 — Selección de Componentes

📎 Navegación: [`README general`](../../README.md) · [`Taller 2`](../README.md) · **Fase 1** · [`Fase 2`](./fase_2_creacion_base_conocimiento.md) · [`Fase 3`](./fase_3_integracion_rag.md)

---

### 1. Modelo de Embeddings para la Vectorización de Documentos

**Modelo seleccionado:** Código abierto (`bge-m3` de Hugging Face) / Propietario (`text-embedding-3-small` de OpenAI).

**Justificación:**
* **Precisión:** Altas puntuaciones en la tabla de clasificación MTEB (Massive Text Embedding Benchmark) para recuperación de información (Retrieval) y similitud semántica.
* **Manejo del Idioma Español:** Excelente capacidad multilingüe nativa, capaz de procesar sinónimos y variaciones en consultas de servicio al cliente en español.
* **Costo y Escalabilidad:** 
  * *Si eliges Open-Source:* Cero costo por token generado; control total de la infraestructura y alineado con los riesgos de privacidad de datos.
  * *Si eliges Propietario:* Costo reducido por consumo sin requerir administración de servidores GPU.

### 2. Almacenamiento Vectorial y Búsqueda por Similitud

**Base de Datos Seleccionada:** [Pinecone / Weaviate / ChromaDB]

#### Análisis Comparativo para EcoMarket:
* **ChromaDB:** Excelente para la fase de prototipado del taller por su nulo costo y facilidad de integración local en Python. Sin embargo, para la escala de EcoMarket en producción requeriría mayor trabajo de infraestructura.
* **Weaviate:** Muy fuerte para el e-commerce gracias a su búsqueda híbrida nativa (combina términos exactos como SKUs con contexto semántico). Es ideal si EcoMarket opta por mantener el control de sus datos autohospedando el servicio.
* **Pinecone:** La opción preferida si se busca reducir el tiempo de salida al mercado (time-to-market). Al ser fully-managed y serverless, escala automáticamente ante picos de demanda en atención al cliente sin requerir administración de servidores.

#### Elección Final y Justificación:
Se elige **[Pinecone / Weaviate]** para el entorno de producción debido a su capacidad de realizar búsquedas vectoriales eficientes combinadas con filtros por metadatos (cruciales para aislar información por usuario o categorías de productos) y su alta escalabilidad ante las miles de consultas diarias de EcoMarket.

---

📎 Continuar con [`Fase 2 — Creación de la Base de Conocimiento`](./fase_2_creacion_base_conocimiento.md)
