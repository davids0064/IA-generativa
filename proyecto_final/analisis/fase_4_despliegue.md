# Fase 4 — Despliegue de la Aplicación

---

En esta fase se empaquetó el agente de la [Fase 2](./fase_2_implementacion_agente.md) y se puso
a disposición de un usuario final mediante una interfaz web. La interfaz no reimplementa
ninguna lógica: usa la misma clase `AgenteDevoluciones` que el chat de consola, de modo que
herramientas, guardas, memoria y auditoría se comportan igual en ambos canales.

## Contenido

- [1. Selección de la herramienta](#1-selección-de-la-herramienta)
- [2. Implementación de la interfaz](#2-implementación-de-la-interfaz)
- [3. Empaquetado y ejecución](#3-empaquetado-y-ejecución)
- [4. Demostración funcional](#4-demostración-funcional)
- [5. Limitaciones del despliegue](#5-limitaciones-del-despliegue)

---

## 1. Selección de la herramienta

| Criterio | Streamlit | Gradio |
| :--- | :--- | :--- |
| Chat | `st.chat_input` y `st.chat_message`. | `gr.ChatInterface`, el más rápido de montar para un chat puro. |
| Mostrar los pasos del agente | `st.expander` y `st.json` por cada herramienta, con su entrada y su resultado. | Posible con mensajes con metadatos, menos flexible para mostrar JSON. |
| Estado por usuario | `st.session_state` guarda el `thread_id` de la conversación. | `gr.State`. |
| Componentes adicionales | Barra lateral, `st.download_button` para la etiqueta PDF, `st.dataframe` para la auditoría y pestañas, en el mismo script. | Requiere `gr.Blocks` para un diseño equivalente. |
| Modelo de programación | Script lineal que se vuelve a ejecutar en cada interacción; no requiere *callbacks*. | Basado en eventos y *callbacks*. |
| Recursos compartidos | `st.cache_resource` mantiene un solo agente por proceso. | Variables globales. |

**Decisión:** se eligió **Streamlit**. La demostración necesita más que un chat: mostrar qué
herramientas usó el agente, descargar la etiqueta generada y consultar el registro de
auditoría, todo en una sola página. Streamlit resuelve esos elementos con componentes nativos y
un script lineal en Python, sin *callbacks*. Gradio habría sido igual de adecuado para un chat
sin esos elementos.

---

## 2. Implementación de la interfaz

La aplicación está en `src/app.py` (versión de Streamlit 1.65).

```
┌───────────────────────┬──────────────────────────────────────────────────────┐
│ Conversación          │  EcoMarket Centro de devoluciones                    │
│ [Nueva conversación]  │  (● Asistente disponible) (● Políticas disponibles)  │
│ Identificador 4c62…   │  Eco es un asistente virtual con IA…                 │
│                       │  [Conversación] [Registro de acciones]               │
│ Casos de prueba       │                                                      │
│ [Elige un caso     ▾] │  👤 Quiero devolver la camiseta ECO-2024-0015…       │
│ [   Enviar caso     ] │  Eco  Tu camiseta se puede devolver… ¿Confirmas?     │
│ ◯ Simular falla       │       (Devolución elegible)                          │
│ ▸ Pedidos de prueba   │       ▸ Detalle técnico                              │
│ ▸ Configuración       │  👤 Sí, confirmo                                     │
│ ───────────────────── │  Eco  ¡Listo! Tu devolución quedó registrada.        │
│ Autores del proyecto  │       (Generó la devolución)                         │
│                       │       ┌╌╌ Etiqueta de devolución ╌╌╌╌╌╌╌╌╌╌╌┐        │
│                       │       ╎ RMA-2026-000001                     ╎        │
│                       │       ╎ Guía · Recolección · Reembolso      ╎        │
│                       │       ╎ ▌▌▍▌▌▍▌▍▌▌▍▌▌▍▌▍▌▌                  ╎        │
│                       │       └╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┘        │
│                       │       [Descargar etiqueta en PDF]                    │
│                       │  [ Escribe tu mensaje                          ➤ ]   │
└───────────────────────┴──────────────────────────────────────────────────────┘
```

| Elemento | Implementación |
| :--- | :--- |
| Campo de texto y área de respuesta | `st.chat_input` y el historial con `st.chat_message`, como pide el enunciado. |
| Acciones del agente | Debajo de cada respuesta, las acciones ejecutadas en lenguaje del usuario (*Consultó el pedido*, *Devolución no elegible*, *Generó la devolución*; en rojo si fallaron) y un desplegable **Detalle técnico** con la entrada y el resultado de cada herramienta en JSON. Permite ver cuándo el agente usó herramientas y cuándo respondió directamente. |
| Etiqueta de devolución | Tarjeta con forma de etiqueta de envío (borde perforado, RMA destacado, transportadora, guía, ventana de recolección y plazo de reembolso) y botón **Descargar etiqueta en PDF**. En las garantías sin devolución física, la tarjeta indica que basta con una foto. |
| Registro de acciones | Pestaña con la auditoría (`logs/auditoria.jsonl`) de la conversación, o de todas, en una tabla. |
| Estado de los servicios | Indicadores en el encabezado ("Asistente disponible", "Políticas sin conexión"…), con un aviso que explica cómo resolverlo si el LLM no responde. Se recalculan cada 30 segundos. |
| Ejemplos | Lista desplegable con los casos de la guía de pruebas; al elegir uno se muestra el mensaje y el botón **Enviar caso** lo envía al chat, de modo que los casos se recorren sin escribirlos. |
| Autores | Botón que abre una ventana con los autores del proyecto y los datos de la asignatura. |
| Simular falla | Interruptor que activa `SIMULAR_FALLA_TRANSPORTADORA` y permite mostrar el manejo de errores. |
| Nueva conversación | Genera un `thread_id` nuevo; el agente empieza sin memoria. |
| Transparencia | El encabezado indica que el cliente habla con un asistente virtual con IA y que puede pedir un asesor humano en cualquier momento. |

**Identidad visual.** La interfaz usa una paleta de verdes fríos asociada a productos
sostenibles: fondo salvia claro (`#F4F6F3`), texto verde bosque (`#17251F`) y verde eucalipto
(`#2D6A55`) como color principal, con la tipografía Instrument Sans. El único color cálido es el
tono kraft de la etiqueta de devolución, que reproduce el aspecto de una etiqueta pegada a una
caja de envío y concentra la atención en el resultado más importante de la conversación. El
tema se define en `.streamlit/config.toml` y los estilos propios (encabezado, acciones del
agente y etiqueta) en `src/app.py`. Se evitaron emojis en los controles y títulos en mayúsculas
para mantener un tono sobrio y profesional.

**Decisiones técnicas:**

- **Un solo agente por proceso** (`st.cache_resource`). Streamlit vuelve a ejecutar el script en
  cada interacción; sin la caché, el agente y su memoria se recrearían en cada mensaje. La memoria
  de cada conversación se separa por `thread_id` guardado en `st.session_state`.
- **La interfaz no maneja errores del LLM por su cuenta.** `AgenteDevoluciones.responder()` ya
  devuelve siempre un texto para el cliente, incluso si el LLM está caído, así que la interfaz
  nunca muestra una traza de Python.
- **Mismo formato de datos que el CLI.** La interfaz lee `RespuestaAgente.pasos` y el campo
  `label_file` del resultado de la herramienta, sin interpretar el texto del LLM.

---

## 3. Empaquetado y ejecución

**Con uv (desarrollo):**

```bash
docker compose up -d chroma        # base vectorial
uv run streamlit run src/app.py    # http://localhost:8501
```

**Con Docker Compose (solución completa):**

```bash
docker compose up -d web           # http://localhost:8501
```

El servicio `web` usa la misma imagen que el resto de la solución y depende de `indexer`, que a
su vez espera a `model-loader` (descarga el LLM del Taller 1, los embeddings y el modelo del
agente) y a `chroma`. Así, un solo comando levanta el LLM, la base vectorial, la carga de la base
de conocimiento y la interfaz. Los directorios `data/` y `logs/` se montan como volúmenes para que
las devoluciones, los tickets, las etiquetas y la auditoría persistan en el equipo anfitrión.

| Archivo | Cambio |
| :--- | :--- |
| `pyproject.toml` / `uv.lock` | Dependencia `streamlit`. |
| `.streamlit/config.toml` | Modo sin navegador, puerto 8501, sin telemetría y color principal verde. |
| `Dockerfile` | Copia la configuración de Streamlit a la imagen. |
| `docker-compose.yml` | Servicio `web` en el puerto 8501. |

---

## 4. Demostración funcional

Recorrido de extremo a extremo, desde la entrada del usuario hasta la respuesta del agente:

| # | Acción en la interfaz | Comportamiento esperado |
| :---: | :--- | :--- |
| 1 | Caso **Saludo** | Respuesta directa, sin herramientas. |
| 2 | Caso **Política de devoluciones** | `consultar_base_conocimiento` y respuesta con el plazo de 5 días hábiles. |
| 3 | Caso **Devolución aceptada** | `verificar_elegibilidad_producto` (elegible) y pregunta de confirmación. |
| 4 | Escribir *"Sí, confirmo"* | `generar_etiqueta_devolucion`: RMA, ventana de recolección y botón para descargar la etiqueta PDF. |
| 5 | Caso **Devolución rechazada** | `verificar_elegibilidad_producto` (no elegible): explica que es un producto de higiene y ofrece la garantía como alternativa. |
| 6 | Caso **Intento de manipulación** | No se genera ninguna etiqueta. |
| 7 | **Nueva conversación**, activar **Simular falla** y repetir 3 y 4 | `SERVICIO_TRANSPORTADORA_NO_DISPONIBLE` y escalamiento a un asesor con ticket. |
| 8 | Pestaña **Registro de acciones** | Auditoría de todas las acciones anteriores. |

Durante la verificación de la interfaz se comprobó que la página carga, que muestra el estado de
los servicios y que procesa un mensaje de ejemplo de punta a punta con el LLM real (ver la
sección 5 sobre la latencia).

---

## 5. Limitaciones del despliegue

| Limitación | Efecto | Mejora propuesta |
| :--- | :--- | :--- |
| Inferencia en CPU (`qwen2.5:7b`) | Un turno con herramientas tarda desde decenas de segundos hasta varios minutos si el equipo tiene poca memoria libre; el primer mensaje incluye la carga del modelo. | GPU o modelo por API (`AGENT_PROVIDER=openai`). |
| Memoria en proceso (`InMemorySaver`) | Las conversaciones se pierden al reiniciar la aplicación. | *Checkpointer* persistente de LangGraph (SQLite o Postgres). |
| Un solo proceso de Streamlit | Las solicitudes simultáneas comparten el mismo modelo local. | Servir el LLM en un servidor de inferencia y escalar la interfaz horizontalmente. |
| Interruptor de falla global | Activar la simulación afecta a todas las sesiones abiertas. | Aceptable para la demostración; no existiría en producción. |
| Sin autenticación | Cualquier persona con un número de seguimiento puede consultar el pedido. | Inicio de sesión del cliente antes de las acciones (Fase 3). |
| Despliegue local | La aplicación corre en el equipo del desarrollador. | Streamlit Community Cloud o Hugging Face Spaces con un LLM por API, ya que Ollama no corre en esos servicios. |
