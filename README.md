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
| **v3** | Proyecto Final | Agente con herramientas que automatiza devoluciones, con guardas, auditoría e interfaz web | [`proyecto_final/README.md`](./proyecto_final/README.md) |

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

### 2.4. Del RAG a un agente que actúa ([Proyecto Final, Fases 1 y 3](./proyecto_final/README.md))

- **RAG como herramienta:** el agente (LangChain `create_agent` sobre LangGraph) decide en
  cada turno si consulta la base de conocimiento, el pedido o ejecuta una acción. Así resuelve
  consultas mixtas ("¿puedo devolver X de mi pedido Y?") que el Taller 2 no cubría.
  [Fase 1](./proyecto_final/analisis/fase_1_diseño_arquitectura.md)
- **Las decisiones críticas no las toma el LLM:** la elegibilidad de una devolución se calcula
  en Python (ventanas de retracto y garantía, exclusiones de higiene y perecederos), lo que
  corrige el error de razonamiento observado en el Taller 2.
- **LLM:** `qwen2.5:7b` en Ollama con temperatura 0, por su soporte de *tool calling* sin
  costo por token; `gpt-4o-mini` por API como alternativa.
- **Riesgos de un agente que actúa:** un error ya no es una respuesta incorrecta sino una
  acción (una RMA, una recolección, un ticket). Las pruebas mostraron que el modelo anunciaba
  acciones sin ejecutarlas e inventaba identificadores; la mitigación son guardas en código,
  confirmación explícita del cliente y un registro de auditoría de cada paso.
  [Fase 3](./proyecto_final/analisis/fase_3_analisis_critico.md)

---

## 3. Resultado de la solución

La solución se construyó en tres versiones incrementales, ejecutables en local con modelos
open-source servidos por **Ollama** (sin costo por token).

```
                v1 — Taller 1                               v2 — Taller 2
consulta ─► db.buscar_pedido ─► prompt ─► LLM      consulta ─► db.buscar_pedido ──────┐
            (dataset.json)      (rol, reglas,                  retriever ChromaDB ─────┤─► PROMPT_RAG ─► LLM ─► JSON
                                 few-shot, JSON)               (políticas, catálogo,   │   (grounding + citas)
                                                                FAQ, filtro por SKU) ──┘

                v3 — Proyecto Final
consulta ─► guardas de entrada ─► agente (LLM con tool calling) ─► guarda de salida ─► respuesta
                                    │  consultar_base_conocimiento (RAG v2)
                                    │  consultar_pedido · verificar_elegibilidad_producto (reglas en código)
                                    │  generar_etiqueta_devolucion (RMA + PDF) · escalar_a_humano (ticket)
                                    └─► logs/auditoria.jsonl
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

### v3 — Agente de devoluciones ([`proyecto_final/`](./proyecto_final/README.md))

- **Cinco herramientas:** consultar la base de conocimiento (el RAG de la v2), consultar un
  pedido, verificar la elegibilidad, generar la etiqueta de devolución (RMA, guía de la
  transportadora y PDF) y escalar a un asesor con un ticket.
- **Guardas en código:** la etiqueta solo se genera si el cliente confirmó en la conversación;
  la herramienta recalcula la elegibilidad (resiste *prompt injection*); repetir una devolución
  devuelve la misma RMA; y un middleware impide que el modelo anuncie acciones que no ejecutó
  o invente números de RMA o de ticket.
- **Sistemas externos simulados** (pedidos, transportadora, mesa de ayuda) con fallas
  controladas, y **auditoría** de cada llamada al LLM y a las herramientas en JSONL.
- **Interfaz web en Streamlit** con la conversación, los pasos del agente, la descarga de la
  etiqueta y el registro de acciones; también se ejecuta con Docker Compose.
  [Fase 4](./proyecto_final/analisis/fase_4_despliegue.md)
- **Pruebas** ([`resultados_pruebas_agente.md`](./proyecto_final/analisis/resultados_pruebas_agente.md)):
  89 pruebas unitarias sin LLM, todas superadas, y una batería de 16 conversaciones con el LLM
  real. Con `qwen2.5:7b` se resolvieron 13 de 16 casos y con `qwen2.5:3b`, 11; **ninguno de
  los dos generó una etiqueta para un pedido no elegible**, ni siquiera ante *prompt injection*.
  Los fallos se concentran en lo que se delega al modelo: no consultó la base de conocimiento
  (respondió plazos inventados) y nunca generó la etiqueta por su cuenta; esa acción la completó
  la guarda en código. La primera ejecución mostró además escalamientos prometidos sin ticket;
  se corrigió la guarda y en la segunda ejecución ninguna respuesta los afirma.

### Limitaciones de la implementación

La implementación se ejecutó en un portátil con `qwen2.5:3b` (4 bits) en el Taller 2 y
`qwen2.5:7b` en el Proyecto Final, con un servidor ChromaDB en Docker, en lugar del LLM de
mayor capacidad y la base vectorial gestionada que se proponen para producción. El modelo
pequeño recupera bien, pero a veces mezcla plazos de políticas distintas; en el agente, la
inferencia en CPU hace que un turno con herramientas tarde desde decenas de segundos hasta
varios minutos. Detalle en
[Limitaciones y suposiciones del Taller 2](./taller_2/README.md#limitaciones-y-suposiciones) y
del [Proyecto Final](./proyecto_final/README.md#limitaciones-y-suposiciones).

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
├── taller_2/          # v2 — RAG (incluye los modos de la v1)
│   ├── README.md      # Fases, ejecución, limitaciones y suposiciones
│   ├── analisis/      # fase_1_seleccion_componentes · fase_2_creacion_base_conocimiento · fase_3_integracion_rag
│   ├── src/ · data/
│   └── pyproject.toml · uv.lock · Dockerfile · docker-compose.yml · .env.example
└── proyecto_final/    # v3 — agente con herramientas (incluye los modos de la v1 y la v2)
    ├── README.md      # Puesta en marcha, interfaz web, guía de pruebas, limitaciones
    ├── analisis/      # fase_1_diseño_arquitectura · fase_2_implementacion_agente · fase_3_analisis_critico
    │                  # fase_4_despliegue · resultados_pruebas_agente · resultados/
    ├── src/ · src/agente/ · tests/ · data/
    └── pyproject.toml · uv.lock · Dockerfile · docker-compose.yml · .env.example
```

Cada versión se ejecuta desde su propia carpeta (`cd taller_1`, `cd taller_2` o
`cd proyecto_final`) siguiendo la sección de puesta en marcha de su README.

---
## Ejemplo funcional de agente Ecomarket

<img width="1520" height="1102" alt="image" src="https://github.com/user-attachments/assets/5861179c-c761-456a-9ee6-83021b634ff8" />

<img width="1520" height="1102" alt="image" src="https://github.com/user-attachments/assets/d9900c6a-c2b7-4769-a2e4-d6eb6bafd4da" />



## Autores

1. Carlos Cepeda
2. David Salamanca

Trabajo desarrollado como parte de la **Maestría**, asignatura *Inteligencia Artificial Generativa*.
