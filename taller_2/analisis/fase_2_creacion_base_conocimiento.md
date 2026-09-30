# Fase 2 — Creación de la Base de Conocimiento

📎 Navegación: [`README general`](../../README.md) · [`Taller 2`](../README.md) · [`Fase 1`](./fase_1_seleccion_componentes.md) · **Fase 2** · [`Fase 3`](./fase_3_integracion_rag.md) · [`Pruebas`](./resultados_pruebas.md)

---

El retriever solo puede devolver lo que existe en la base de conocimiento, y lo devuelve
en las unidades en que se cortó. Por eso **qué documentos se incluyen, con qué calidad y
cómo se dividen** determina directamente si el agente de EcoMarket recibe la regla
correcta o un fragmento que la mezcla con otras. Esta fase define esas tres decisiones y
las valida con datos.

## Contenido

- [1. Documentos identificados](#1-documentos-identificados)
- [2. Calidad de los documentos](#2-calidad-de-los-documentos)
- [3. Estrategia de segmentación (chunking)](#3-estrategia-de-segmentación-chunking)
- [4. Metadatos](#4-metadatos)
- [5. Pipeline de indexación](#5-pipeline-de-indexación)
- [6. Validación: cómo afecta el chunking al rendimiento del RAG](#6-validación-cómo-afecta-el-chunking-al-rendimiento-del-rag)

---

## 1. Documentos identificados

El 80 % de las consultas repetitivas de EcoMarket son sobre **pedidos, devoluciones y
productos**. Cada tipo de documento cubre una parte de esas preguntas:

| # | Documento | Formato | Contenido | Preguntas que responde | Frecuencia de cambio |
| :---: | :--- | :--- | :--- | :--- | :--- |
| 1 | **Manual de políticas y garantías** ([`manual_politicas_garantias.md`](../data/conocimiento/manual_politicas_garantias.md)) | Texto narrativo con secciones (Markdown; el pipeline también acepta PDF) | 7 secciones: envíos, retrasos e incidencias, cancelaciones, devoluciones (retracto, garantía, reembolsos), garantía de tecnología, privacidad, atención humana | "¿Puedo devolver…?", "¿Cuánto tarda el reembolso?", "¿Me devuelven el envío por el retraso?" | Baja (cambios de política) |
| 2 | **Catálogo de productos** ([`catalogo_productos.json`](../data/conocimiento/catalogo_productos.json)) | Datos estructurados (JSON; un CSV funcionaría igual) | 18 productos en 6 categorías, con SKU, precio, stock, certificaciones y las banderas "perecedero" e "higiene personal" | "¿Tienen cargadores solares?", "¿Cuánto cuesta…?", "¿Está disponible?" | Alta (precios y stock) |
| 3 | **Preguntas frecuentes (FAQ)** ([`faq.json`](../data/conocimiento/faq.json)) | Pares pregunta-respuesta (JSON) | 13 preguntas en 7 categorías: pedidos, envíos, devoluciones, productos, suscripciones, pagos, sostenibilidad | "¿Aceptan Nequi?", "¿Hacen envíos internacionales?", "¿Cómo cancelo mi suscripción?" | Media |

**Documento que deliberadamente NO se vectoriza: los pedidos** ([`dataset.json`](../data/dataset.json)).
El estado de un pedido cambia a diario, se consulta por coincidencia exacta del número
de seguimiento y contiene datos personales (nombres, direcciones). Por eso se consulta
con búsqueda estructurada (`db.buscar_pedido`) y se inyecta aparte en el prompt. Una
búsqueda semántica podría devolver el pedido *parecido* de otro cliente, y un índice
vectorial con datos personales amplía la superficie de exposición (riesgo de privacidad
del Taller 1, Fase 2).

**Documentos candidatos para una siguiente iteración:** manuales de uso de los
productos (instalación del panel solar, mantenimiento de la compostera), términos y
condiciones, e historial de conversaciones resueltas por los asesores, previa
anonimización.

---

## 2. Calidad de los documentos

Un RAG responde con total seguridad lo que diga su base de conocimiento, incluso si
está mal (*garbage in, garbage out*). Por eso los documentos se prepararon con estos
criterios antes de indexarlos:

| Criterio | Aplicación | Por qué afecta al RAG |
| :--- | :--- | :--- |
| **Una sola fuente de verdad por regla** | Los plazos (5 días hábiles de retracto, 30 días de garantía, 5–10 días de reembolso) están definidos en el manual; las FAQ los repiten con las mismas cifras. Se alinearon con la política de devoluciones del Taller 1. | Si la FAQ y el manual dijeran cifras distintas, el retriever podría traer cualquiera de las dos y el LLM respondería de forma inconsistente. |
| **Estructura explícita** | El manual usa encabezados numerados (`##`, `###`), una regla por viñeta. | Los encabezados son las fronteras naturales de corte y quedan como metadatos para citar y filtrar (sección 3). |
| **Lenguaje del cliente en las FAQ** | Las preguntas están redactadas como las haría un cliente. | La consulta del cliente se parece más a la pregunta de la FAQ que a un texto normativo, lo que mejora la similitud. |
| **Datos estructurados completos** | Cada producto tiene todos sus campos, incluidas las banderas `is_perishable` e `is_hygiene_item`. | Esos campos deciden si un producto admite devolución; un dato faltante produce una respuesta errónea. |
| **Sin datos personales** | Ninguno de los tres documentos contiene información de clientes. | El índice vectorial puede compartirse y replicarse sin exponer datos personales. |
| **Frescura** | El stock del catálogo es una foto del momento de la indexación. | Un stock desactualizado produce respuestas incorrectas; en producción el catálogo debe reindexarse periódicamente (sección 5). |

---

## 3. Estrategia de segmentación (chunking)

Cada tipo de documento se divide según su estructura. Un único tamaño fijo para todo
mezclaría reglas distintas en un mismo fragmento o partiría una regla de sus excepciones.

| Documento | Estrategia | Parámetros | Resultado |
| :--- | :--- | :--- | :--- |
| Manual de políticas | **Por encabezados** (`MarkdownHeaderTextSplitter`) y, como red de seguridad, **recursivo** (`RecursiveCharacterTextSplitter`) | Corte en `#`, `##`, `###`; máximo 500 tokens, solapamiento de 50 | 11 chunks de 29 a 238 tokens (promedio 113): **cada sección queda completa en un solo chunk** |
| Catálogo | **Un producto = un chunk**, convertido de JSON a texto natural | Sin tamaño máximo (cada ficha es corta) | 18 chunks de 73 a 97 tokens |
| FAQ | **Una pregunta con su respuesta = un chunk** | Sin tamaño máximo | 13 chunks de 29 a 84 tokens |
| **Total** | | | **42 chunks, unos 3.500 tokens** |

### 3.1. Manual de políticas: corte por encabezados

- **Por qué por encabezados:** en el manual, la unidad de significado es la sección. La
  sección 4.1 (derecho de retracto) contiene la ventana de 5 días hábiles **y** la lista
  de productos excluidos. Si un corte las separa, el retriever puede traer la ventana sin
  las exclusiones, y el agente aceptaría devolver un cepillo de dientes.
- **Por qué 500 tokens de máximo:** es un límite de seguridad para secciones futuras más
  largas. Las secciones actuales miden entre 29 y 238 tokens, así que ninguna se corta.
  Es holgado para `bge-m3` (8.192 tokens) y mantiene el prompt pequeño.
- **Por qué 50 tokens de solapamiento (10 %):** si alguna sección llega a superar los 500
  tokens, la frase del borde queda en ambos fragmentos y no pierde su contexto. Hoy no
  se aplica porque ninguna sección se parte.
- **Encabezado dentro del texto** (`strip_headers=False`): el título "4.1 Derecho de
  retracto" forma parte del contenido embebido y sirve de ancla semántica para consultas
  como "me arrepentí de la compra".

### 3.2. Catálogo: un registro por chunk, en texto natural

- **Por qué un registro por chunk:** cada producto es independiente. Juntar varios en un
  chunk haría que la consulta por uno trajera también otros, y no se podría filtrar por
  SKU.
- **Por qué convertir el JSON a texto:** los modelos de embeddings se entrenan con
  lenguaje natural; llaves, comillas y nombres de campo en inglés (`"is_hygiene_item":
  true`) añaden ruido. La ficha se escribe como "Perecedero: no | Higiene personal: sí".

  ```text
  Producto: Cepillo de dientes de bambú (pack x4) (SKU ECO-HIG-004)
  Categoría: Higiene personal
  Precio: $24.900 COP
  Disponibilidad: 320 unidades
  Perecedero: no | Higiene personal: sí
  Certificaciones: FSC
  Descripción: Mango de bambú Moso biodegradable y cerdas de nailon libre de BPA. ...
  ```

### 3.3. FAQ: pregunta y respuesta juntas

La pregunta se embebe junto con su respuesta: la pregunta aporta la similitud con la
consulta del cliente, y la respuesta aporta el contenido que usará el LLM. Separarlas
produciría fragmentos de preguntas sin respuesta.

---

## 4. Metadatos

Cada chunk guarda metadatos que el agente usa para **citar la fuente** y para
**filtrar** sin depender de la similitud semántica:

| Metadato | Presente en | Uso en el sistema |
| :--- | :--- | :--- |
| `fuente` (`politicas`, `catalogo`, `faq`) | Todos | Etiqueta de cada fragmento en el prompt y en `sources_used` |
| `documento` | Todos | Trazabilidad al archivo de origen |
| `seccion`, `subseccion` | Manual | **Filtro:** el agente de devoluciones trae siempre las secciones 4.1, 4.2, 4.3 y 5 según el motivo y el estado del pedido |
| `sku` | Catálogo | **Filtro:** la ficha del producto del pedido se recupera por SKU exacto |
| `categoria` | Catálogo y FAQ | Filtros por categoría (por ejemplo, solo Tecnología) |
| `stock` | Catálogo | Disponibilidad sin depender del texto |

Los identificadores son deterministas (`politicas-006`, `catalogo-ECO-TEC-078`,
`faq-011`): reindexar actualiza los mismos registros en lugar de duplicarlos.

---

## 5. Pipeline de indexación

Implementado en [`src/base_conocimiento.py`](../src/base_conocimiento.py). Se ejecuta
**una sola vez** con el servicio `indexer` de Docker Compose o con
`uv run python -m src.base_conocimiento`; los agentes solo consultan.

```
1. Extracción     manual (.md o .pdf con pypdf) · catálogo (JSON) · FAQ (JSON)
2. Normalización  JSON → texto natural; metadatos escalares (requisito de ChromaDB)
3. Segmentación   manual: encabezados + recursivo (500/50) · catálogo y FAQ: 1 registro = 1 chunk
4. Vectorización  bge-m3 (Fase 1), el mismo modelo que usarán las consultas
5. Upsert         vector + texto + metadatos en ChromaDB, con ids deterministas
```

**Mantenimiento:** si cambia un documento o el modelo de embeddings, se reconstruye con
`--reindexar`. En producción, el catálogo (precios y stock) debería reindexarse de forma
programada, por ejemplo cada noche, mientras que el manual solo cuando cambie una política.

---

## 6. Validación: cómo afecta el chunking al rendimiento del RAG

Para medir el efecto de esta estrategia se comparó con la alternativa ingenua: cortar
los tres archivos en bruto cada 500 tokens, sin respetar encabezados ni registros. La
evaluación ([`src/evaluacion_recuperacion.py`](../src/evaluacion_recuperacion.py), las
mismas 20 consultas en español de la
[Fase 1](./fase_1_seleccion_componentes.md#12-evidencia-propia-evaluación-de-recuperación-en-español))
arroja:

| Modelo | Chunking | Chunks | hit@1 | hit@4 | MRR@4 | Tokens que recibe el LLM (top-4) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| `bge-m3` | **Estructurada (esta fase)** | 42 | **80 %** | **100 %** | **0,89** | **350** |
| `bge-m3` | Tamaño fijo (500 tokens) | 11 | 55 % | 95 % | 0,68 | 1.654 |
| `nomic-embed-text-v2-moe` | Estructurada | 42 | 65 % | 95 % | 0,77 | 350 |
| `nomic-embed-text-v2-moe` | Tamaño fijo (500 tokens) | 11 | 70 % | 100 % | 0,81 | 1.687 |

```bash
uv run python -m src.evaluacion_recuperacion --modelos bge-m3 nomic-embed-text-v2-moe
```

**Lectura de los resultados:**

1. **Precisión:** con el modelo elegido, el chunking estructurado pone el fragmento
   correcto en primer lugar en el 80 % de las consultas, frente al 55 % del tamaño fijo.
2. **El hit@4 del tamaño fijo es engañoso.** Hay solo 11 fragmentos de unos 450 tokens,
   así que recuperar 4 equivale a traer más de un tercio de toda la base. "Acertar" es
   casi inevitable, pero el LLM recibe **4,7 veces más texto** (1.654 frente a 350
   tokens), en su mayoría irrelevante. Por la misma razón, `nomic` obtiene un hit@1
   ligeramente mayor con tamaño fijo: fragmentos más grandes contienen más frases por
   coincidencia.
3. **Mezcla de reglas.** Con tamaño fijo, un solo fragmento del manual abarca desde la
   sección 3 (cancelaciones) hasta la 5 (garantía de tecnología): retracto de 5 días
   hábiles, garantía de 30 días y garantía de fabricante de 12 meses juntas. Es
   exactamente la confusión que tuvo el modelo de 3B en el
   [caso 3 de las pruebas](./resultados_pruebas.md#caso-3--panel-solar-defectuoso-a-los-22-días-pedido-eco-2024-0008),
   aun con fragmentos bien separados. Mezclarlas desde la base de conocimiento empeoraría
   el problema.
4. **Presupuesto de contexto.** Sin los fragmentos, el prompt de devoluciones (reglas y
   ejemplos) ya ocupa más de 3.000 tokens, según el tokenizador del modelo. Sumarle 1.650
   tokens de contexto superaría el contexto por defecto de Ollama (4.096 tokens) y el
   modelo no alcanzaría a responder; con 350 tokens sí cabe.
5. **Filtros imposibles.** Un fragmento de tamaño fijo no pertenece a una sección ni a un
   producto, así que no puede llevar metadatos de `seccion` o `sku`. Sin ellos no existen
   las recuperaciones garantizadas que usa el agente de devoluciones.

**Conclusión:** la segmentación por estructura no es un detalle de implementación.
Mejora la precisión del retriever, reduce el contexto que procesa el LLM a menos de una
cuarta parte, evita que el modelo vea reglas contradictorias juntas y habilita los
filtros por metadatos. **Limitación de la validación:** 20 consultas es una muestra
pequeña; el mismo script admite ampliar el conjunto sin cambios.

---

📎 Continuar con [`Fase 3 — Integración y Ejecución del Código`](./fase_3_integracion_rag.md)
