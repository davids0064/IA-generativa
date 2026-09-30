# IA Generativa — Atención al Cliente de EcoMarket

**Caso de estudio:** optimización de la atención al cliente en **EcoMarket**, una empresa
de e-commerce de productos sostenibles.

Este repositorio reúne los talleres prácticos de la asignatura **Inteligencia Artificial
Generativa** (Maestría). Cada taller es una **versión** de la misma solución y vive en su
propia carpeta, con su documentación, su código y su entorno de ejecución independientes.
Este documento resume el análisis del problema y el resultado final; el detalle está en el
README de cada taller.

| Versión | Taller | Qué aporta | Documentación |
| :---: | :--- | :--- | :--- |
| **v1** | Taller Práctico #1 | Selección del modelo, análisis de riesgos e ingeniería de prompts | [`taller_1/README.md`](./taller_1/README.md) |
| **v2** | Taller Práctico #2 | Sistema RAG: base de conocimiento vectorial con LangChain + ChromaDB | [`taller_2/README.md`](./taller_2/README.md) |

---

## 1. El problema

El departamento de soporte de EcoMarket recibe miles de consultas diarias por chat, correo
y redes sociales, con un **tiempo de respuesta promedio de 24 horas**:

- El **80 %** son **repetitivas**: estado del pedido, devoluciones, características de productos.
- El **20 %** son **complejas**: quejas, problemas técnicos o sugerencias que requieren empatía y criterio humano.

El objetivo es diseñar una solución de IA generativa que acelere y mejore la calidad de
esas respuestas.

---

## 2. Análisis

### 2.1. Modelo y arquitectura ([Taller 1, Fase 1](./taller_1/analisis/fase_1_seleccion_modelo.md))

Se propone una **solución híbrida**:

- **Autopilot (80 % repetitivo):** un LLM ligero y de baja latencia con **RAG** que consulta
  en tiempo real los sistemas de EcoMarket (pedidos, catálogo, políticas) y responde solo
  con esa información.
- **Copiloto humano (20 % complejo):** la conversación se transfiere a un agente humano,
  asistido por un modelo de mayor razonamiento que resume el caso y sugiere una respuesta empática.

Se descarta el **fine-tuning** como fuente de datos: los pedidos cambian cada minuto y un
modelo afinado inventaría estados que no conoce. RAG ofrece precisión factual, no requiere
reentrenar cuando cambia el catálogo y escala con el volumen a bajo costo.

### 2.2. Fortalezas, limitaciones y riesgos ([Taller 1, Fase 2](./taller_1/analisis/fase_2_evaluacion.md))

| Aspecto | Conclusión |
| :--- | :--- |
| **Fortalezas** | Respuesta de 24 h a segundos, disponibilidad 24/7, tono consistente y menor costo por ticket. |
| **Limitaciones** | No tiene empatía real, depende de la calidad de los datos (*garbage in, garbage out*) y no resuelve casos no documentados. |
| **Alucinaciones** | Se mitigan con *grounding* estricto al contexto recuperado y temperatura baja (0.0 – 0.2). |
| **Sesgo** | Se mitiga con auditorías de prompts, *red-teaming* y guías de estilo neutras. |
| **Privacidad** | Enmascaramiento de datos personales y contratos sin retención de datos; los pedidos no se vectorizan. |
| **Impacto laboral** | *Human-in-the-loop*: la IA absorbe lo repetitivo y los agentes se enfocan en los casos complejos. |

### 2.3. Componentes del RAG ([Taller 2, Fases 1 y 2](./taller_2/README.md))

- **Embeddings:** `bge-m3` (open-source, multilingüe, contexto de 8K tokens). En una
  evaluación propia con 20 consultas coloquiales en español recuperó el fragmento
  correcto en primer lugar en el 80 % de los casos, frente al 65 % de la alternativa
  evaluada. Se ejecuta en infraestructura propia (privacidad), con `text-embedding-3-small`
  como alternativa gestionada. [Fase 1](./taller_2/analisis/fase_1_seleccion_componentes.md)
- **Base vectorial:** ChromaDB en modo servidor para el prototipo (costo cero, filtros por
  metadatos); Weaviate autohospedado para producción, por su búsqueda híbrida nativa
  (SKU + semántica), réplicas y control de los datos.
- **Base de conocimiento:** manual de políticas y garantías, catálogo de productos y FAQ
  (42 chunks). Los pedidos no se vectorizan: se consultan por búsqueda exacta.
- **Chunking:** por estructura. El manual se corta por encabezados (cada sección completa
  en un chunk, con un máximo de 500 tokens y 50 de solapamiento), y catálogo y FAQ van a
  un registro por chunk. Frente a cortar cada 500 tokens, sube el hit@1 de 55 % a 80 % y
  reduce 4,7 veces el contexto que recibe el LLM.
  [Fase 2](./taller_2/analisis/fase_2_creacion_base_conocimiento.md)

---

## 3. Resultado de la solución

La solución se construyó en dos versiones incrementales, ejecutables en local con modelos
open-source servidos por **Ollama** (sin costo por token).

```
                v1 — Taller 1                               v2 — Taller 2
consulta ─► db.buscar_pedido ─► prompt ─► LLM      consulta ─► db.buscar_pedido ──────┐
            (dataset.json)      (rol, reglas,                  retriever ChromaDB ─────┤─► PROMPT_RAG ─► LLM ─► JSON
                                 few-shot, JSON)               (políticas, catálogo,   │   (grounding + citas)
                                                                FAQ, filtro por SKU) ──┘
```

### v1 — Ingeniería de prompts ([`taller_1/`](./taller_1/README.md))

- **Estado de un pedido:** comparación entre un prompt básico, que alucina porque no tiene
  datos, y un prompt mejorado con rol, datos del pedido inyectados, reglas por estado,
  ejemplos *few-shot* y salida JSON estructurada.
- **Devoluciones:** el prompt aplica la política de EcoMarket (retracto, garantía, productos
  perecederos y de higiene) mediante un árbol de decisión. Los días transcurridos los calcula
  el código para evitar errores aritméticos del modelo.
- Base de datos simulada de 14 pedidos que cubre todos los estados.

### v2 — Sistema RAG ([`taller_2/`](./taller_2/README.md))

- Base de conocimiento de **42 chunks** (11 de políticas, 18 productos, 13 FAQ) indexada con `bge-m3` en ChromaDB.
- El agente combina el registro del pedido con los fragmentos recuperados, **cita sus fuentes**
  (`sources_used`) y marca `answer_grounded: false` y escala a un humano cuando no encuentra respaldo.
- **Pruebas de la entrega** ([`resultados_pruebas.md`](./taller_2/analisis/resultados_pruebas.md)):
  2 de 4 casos resueltos correctamente (exclusión de productos de higiene en el agente
  general y en el de devoluciones). En los otros 2 el agente no inventó información:
  marcó la respuesta como no fundamentada y escaló a un asesor. Uno falló en la
  recuperación (la política de retrasos no llegó al contexto) y otro en el razonamiento
  del modelo de 3B (confundió dos garantías con la regla correcta a la vista). El
  documento incluye las capturas, el resultado esperado de cada caso y las mejoras propuestas.

### Limitaciones de la implementación

La implementación se ejecutó en un portátil con `qwen2.5:3b` (4 bits) y un servidor ChromaDB en Docker, en
lugar del LLM de mayor capacidad y la base vectorial gestionada que se proponen para
producción. El modelo pequeño recupera bien, pero a veces mezcla plazos de políticas
distintas. Detalle en
[Limitaciones y suposiciones del Taller 2](./taller_2/README.md#limitaciones-y-suposiciones).

---

## Estructura del repositorio

```
IA-generativa/
├── README.md          # Este archivo: análisis y resultado general
├── taller_1/          # v1 — prompts (sin RAG)
│   ├── README.md      # Enunciado, fases, ejecución
│   ├── analisis/      # fase_1_seleccion_modelo · fase_2_evaluacion · fase_3_prompts
│   ├── src/ · data/
│   └── pyproject.toml · uv.lock · Dockerfile · docker-compose.yml · .env.example
└── taller_2/          # v2 — RAG (incluye los modos de la v1)
    ├── README.md      # Fases, ejecución, limitaciones y suposiciones
    ├── analisis/      # fase_1_seleccion_componentes · fase_2_creacion_base_conocimiento · fase_3_integracion_rag
    ├── src/ · data/
    └── pyproject.toml · uv.lock · Dockerfile · docker-compose.yml · .env.example
```

Cada versión se ejecuta desde su propia carpeta (`cd taller_1` o `cd taller_2`) siguiendo
la sección de puesta en marcha de su README.

---

## Autores

1. Carlos Cepeda
2. David Salamanca

Trabajo desarrollado como parte de la **Maestría**, asignatura *Inteligencia Artificial Generativa*.
