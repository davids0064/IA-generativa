# Taller Práctico #1 — IA Generativa

**Caso de Estudio:** Optimización de la Atención al Cliente en **EcoMarket** (empresa de e-commerce de productos sostenibles).

Este repositorio contiene la resolución del Taller Práctico #1 de la asignatura de **Inteligencia Artificial Generativa**. La solución se ha dividido en archivos independientes para facilitar su lectura, evaluación y mantenimiento por etapas.

---

## Navegación

### Contexto general
- [**Contexto del Taller**](./context.md) — Enunciado del caso de estudio y estructura completa del taller.

### Soluciones por fase
| Fase | Descripción | Documento |
| :---: | :--- | :--- |
| **1** | Selección y Justificación del Modelo de IA | [`fase_1_seleccion_modelo.md`](./fase_1_seleccion_modelo.md) |
| **2** | Evaluación de Fortalezas, Limitaciones y Riesgos Éticos | [`fase_2_evaluacion.md`](./fase_2_evaluacion.md) |
| **3** | Aplicación de la Ingeniería de Prompts | [`fase_3_prompts.md`](./fase_3_prompts.md) |

### Taller Práctico #2 — Sistema RAG
| Fase | Descripción | Documento |
| :---: | :--- | :--- |
| **1** | Selección de componentes (embeddings y base vectorial) | [`taller_2/fase_1_seleccion_componentes.md`](./taller_2/fase_1_seleccion_componentes.md) |
| **2** | Creación de la base de conocimiento (ingesta, chunking, indexación) | [`taller_2/fase_2_creacion_base_conocimiento.md`](./taller_2/fase_2_creacion_base_conocimiento.md) |
| **3** | Integración y ejecución del código (LangChain + ChromaDB) | [`taller_2/fase_3_integracion_rag.md`](./taller_2/fase_3_integracion_rag.md) |

Las limitaciones y suposiciones de la implementación están en [Limitaciones y suposiciones del Taller 2](#limitaciones-y-suposiciones-del-taller-2).

---

## Estructura del repositorio

```
IA-generativa/
├── README.md                       # Índice principal (este archivo)
├── context.md                      # Caso de uso + estructura del taller
├── fase_1_seleccion_modelo.md      # Solución Fase 1
├── fase_2_evaluacion.md            # Solución Fase 2
├── fase_3_prompts.md               # Solución Fase 3 (prompts + código)
├── taller_2/                       # Soluciones del Taller 2 (RAG)
│   ├── fase_1_seleccion_componentes.md
│   ├── fase_2_creacion_base_conocimiento.md
│   └── fase_3_integracion_rag.md
├── data/
│   ├── dataset.json                # Pedidos (base de datos simulada, Taller 1)
│   ├── conocimiento/               # Base de conocimiento del RAG (Taller 2)
│   │   ├── manual_politicas_garantias.md
│   │   ├── catalogo_productos.json
│   │   └── faq.json
│   └── vectorstore/                # Índice de ChromaDB (generado, no versionado)
└── src/
    ├── main.py                     # Agente: prompts básico/mejorado + modo RAG
    ├── main_devolucion.py          # Agente de devoluciones (Taller 1)
    ├── llm.py · db.py              # Cliente del LLM y acceso a pedidos
    ├── prompts.py · prompts_devolucion.py
    ├── base_conocimiento.py        # Pipeline de indexación (Taller 2)
    ├── rag.py                      # Retriever + cadena LangChain (Taller 2)
    └── prompts_rag.py              # Prompt del agente con RAG (Taller 2)
```

---

## Autores
1. Carlos Cepeda
2. David Salamanca

Trabajo desarrollado como parte de la **Maestría** — Asignatura *Inteligencia Artificial Generativa*.

## Puesta en marcha y pruebas

> Guía rápida con capturas de una ejecución real. El paso a paso completo (comandos, variables de entorno, Docker Compose) está documentado en el [punto 3 — Código ejecutable de la Fase 3](./fase_3_prompts.md#3-código-ejecutable).

### 1. Instalación de dependencias

`pip install -r requirements.txt`

<img width="1070" height="478" alt="Instalación de dependencias de Python" src="https://github.com/user-attachments/assets/70aa8dc7-273a-4a0a-92e4-10a6865e0e5f" />

### 2. Modelo Ollama corriendo

Servidor local levantado con `docker compose up -d ollama model-loader`, verificado en `http://localhost:11434/`.

<img width="1461" height="637" alt="Servidor de Ollama corriendo en local" src="https://github.com/user-attachments/assets/63224e9c-3c1d-418c-a6fd-345da57f3351" />

### 3. Pruebas

#### 3.1. Base de datos simulada

`python -m src.main --listar` — confirma que hay pedidos cargados antes de probar los prompts.

<img width="866" height="270" alt="Listado de pedidos de la base de datos simulada" src="https://github.com/user-attachments/assets/c891a9e9-93b4-46ab-9d54-ab619c13c2f7" />

#### 3.2. Ejercicio 1 — Estado de un pedido

`python -m src.main --tracking <tracking>` — muestra la diferencia entre el **prompt básico** (sin rol ni contexto) y el **prompt mejorado** (RAG + reglas + JSON estructurado). Detalle en la [sección 1](./fase_3_prompts.md#1-prompt-de-solicitud-de-pedido).

<img width="822" height="674" alt="Comparación entre el prompt básico y el prompt mejorado" src="https://github.com/user-attachments/assets/a62138d3-8503-4dd4-9398-4ba9d44fe22f" />

#### 3.3. Ejercicio 2 — Devolución de un producto

`python -m src.main_devolucion --listar` — atributos relevantes para decidir la elegibilidad (categoría, perecedero, higiene, fecha de entrega). Detalle en la [sección 2](./fase_3_prompts.md#2-prompt-de-devolución-de-producto).

<img width="878" height="284" alt="Atributos relevantes para evaluar una devolución" src="https://github.com/user-attachments/assets/cf074621-69e2-4659-a141-75d75a871af1" />

`python -m src.main_devolucion --tracking <tracking> --motivo <motivo>` — evalúa la solicitud contra la política de devoluciones y responde con el JSON estructurado.

<img width="1068" height="774" alt="Prueba de solicitud de devolución de un producto" src="https://github.com/user-attachments/assets/d74101a7-a6c4-49af-a245-d117cba96b78" />

#### 3.4. Taller 2 — Agente con RAG

```bash
ollama pull bge-m3                          # modelo de embeddings (o docker compose up -d ollama model-loader)
python -m src.main --indexar                # construye el índice en data/vectorstore
python -m src.main --modo rag --consulta "¿Puedo devolver un jabón que ya abrí?"
python -m src.main --modo rag --tracking ECO-2024-0004 --consulta "¿Me devuelven el envío por el retraso?"
```

La salida muestra el pedido asociado, los fragmentos recuperados con su fuente y la
respuesta estructurada con las citas usadas (`sources_used`). Detalle y resultados
en [`taller_2/fase_3_integracion_rag.md`](./taller_2/fase_3_integracion_rag.md).

---

## Limitaciones y suposiciones del Taller 2

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
   privacidad del Taller 1, Fase 2.
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
   [`fase_3_integracion_rag.md`](./taller_2/fase_3_integracion_rag.md), sin métricas
   como RAGAS.
