# Fase 2 — Creación de la Base de Conocimiento

📎 Navegación: [`README general`](../../README.md) · [`Taller 2`](../README.md) · [`Fase 1`](./fase_1_seleccion_componentes.md) · **Fase 2** · [`Fase 3`](./fase_3_integracion_rag.md)

---

### Estrategia de Ingesta, Chunking e Indexación

#### Documentos Identificados
1. **Manual de Políticas y Garantías (PDF):** Reglas de negocio para devoluciones y envíos.
2. **Catálogo e Inventario de Productos (CSV/JSON):** Especificaciones técnicas, categorías y stock.
3. **Base de Conocimiento de FAQ (JSON):** Respuestas predefinidas a preguntas frecuentes.

#### Estrategia de Chunking
* **Textos narrativos/Políticas:** *Recursive Character Text Splitter* (500 tokens por chunk, overlap de 50 tokens) para conservar el contexto completo de cada regla de negocio.
* **Datos estructurados (Inventario y FAQs):** *Document-based Chunking* (1 registro o producto = 1 chunk completo con sus metadatos integrados).

#### Pipeline de Indexación
1. **Extracción:** Lectura y filtrado de los documentos de origen.
2. **Segmentación:** Creación de fragmentos lógicos mediante chunking recursivo o estructurado.
3. **Vectorización:** Generación de embeddings densos mediante el modelo seleccionado.
4. **Almacenamiento (Upsert):** Carga del vector, el texto de respaldo y los metadatos asociados en la base de datos vectorial seleccionada.

---

📎 Continuar con [`Fase 3 — Integración y Ejecución del Código`](./fase_3_integracion_rag.md)
