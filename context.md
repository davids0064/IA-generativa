# Contexto del Taller

> Documento de referencia con el enunciado íntegro del **Taller Práctico #1** y la estructura de las fases que se van a resolver en este repositorio.

Volver al [`README.md`](./README.md)

---

## 1. Caso de Estudio: Optimización de la Atención al Cliente en una Empresa de E-commerce

El caso de estudio que abordaremos se centra en **"Acelerar y mejorar la calidad de las respuestas en el servicio de atención al cliente"** de una empresa de comercio electrónico.

La empresa, llamada **"EcoMarket"**, vende productos sostenibles y está experimentando un rápido crecimiento. Han notado un cuello de botella en su departamento de soporte, que recibe miles de consultas diarias a través de chat, correo electrónico y redes sociales.

- El **80%** de estas consultas son **repetitivas** (estado del pedido, devoluciones, características del producto).
- El **20% restante** son más **complejas**, requiriendo un toque humano y empatía (quejas, problemas técnicos, sugerencias).

Actualmente, el tiempo de respuesta promedio es de **24 horas**, lo que está afectando la satisfacción del cliente.

**Objetivo del taller:** Los estudiantes deben diseñar una **solución de IA generativa** para este problema.

---

## 2. Estructura del Taller

El taller se dividirá en **tres fases**, cada una correspondiente a los puntos clave de la descripción proporcionada.

### Fase 1 — Selección y Justificación del Modelo de IA
Los estudiantes deberán seleccionar y justificar un modelo de IA generativa para resolver el problema de EcoMarket. **No hay una única respuesta correcta**; lo importante es la justificación.

**Preguntas guía:**
- ¿Qué tipo de modelo de IA generativa es el más adecuado? *(ej: un LLM como GPT-4, un modelo de lenguaje pequeño afinado (Fine-tuned LLM), o una solución híbrida).*
- ¿Por qué este modelo y no otro? Consideren la necesidad de **precisión** para temas de pedidos vs. la necesidad de **fluidez** para respuestas a preguntas generales.
- ¿Cuál sería la **arquitectura propuesta**? ¿El modelo se integraría con la base de datos de EcoMarket (catálogo de productos, información de envíos)? ¿Sería un modelo de propósito general o se afinaría con datos de la empresa?
- **Justificación:** presentar argumentos basados en criterios como **costo, escalabilidad, facilidad de integración** y **calidad de la respuesta** esperada.

➡️ Solución: [`fase_1_seleccion_modelo.md`](./fase_1_seleccion_modelo.md)

---

### Fase 2 — Evaluación de Fortalezas, Limitaciones y Riesgos Éticos
Aquí el **pensamiento crítico** es fundamental. Los estudiantes no solo deben elegir una solución, sino también evaluar sus implicaciones.

**Puntos a considerar:**
- **Fortalezas:** ¿Qué haría bien el modelo propuesto? *(reducción del tiempo de respuesta, disponibilidad 24/7, manejo del 80% repetitivo, etc.).*
- **Limitaciones:** ¿Qué no podría hacer? *(no puede manejar el 20% complejo que requiere empatía; podría responder mal si la información de la BD es incorrecta).*
- **Riesgos Éticos:**
    - **Alucinaciones:** el modelo podría inventar información sobre pedidos o productos.
    - **Sesgo:** podría reflejar sesgos de los datos de entrenamiento, favoreciendo a ciertos grupos.
    - **Privacidad de datos:** ¿cómo se maneja información sensible (direcciones, historial de compras) al usarse como contexto o para fine-tuning?
    - **Impacto laboral:** ¿qué pasa con los agentes humanos? ¿El objetivo es reemplazarlos o empoderarlos?

Solución: [`fase_2_evaluacion.md`](./fase_2_evaluacion.md)

---

### Fase 3 — Aplicación de la Ingeniería de Prompts
En esta fase **práctica**, los estudiantes diseñarán prompts para su modelo, para entender la conexión directa entre la instrucción y el resultado.

Se utilizará una estructura similar a la abordada en el tutorial práctico de prompts de la primera sesión. La idea es evidenciar, en código, cómo se construye una cadena de prompts para obtener respuestas óptimas en las interacciones con el chat de atención al cliente.

> **Nota:** Aunque en las primeras fases se puede proponer un modelo complejo o de pago, para este ejercicio pueden usar un modelo **open-source** sin ningún problema, con el fin de evidenciar el impacto de los prompts.

**Ejercicios de prompts:**
1. **Prompt de Solicitud de Pedido:** Redactar un prompt que le pida al modelo el estado de un pedido, proporcionando el número de seguimiento. Deben crear un documento/texto con el estado de **mínimo 10 pedidos** que actuará como base de datos.
   - *Ejemplo básico:* `"Dame el estado del pedido 12345."`
   - *Ejemplo mejorado:* `"Actúa como un agente de servicio al cliente amable. Proporciona el estado actual del pedido con el número de seguimiento '{{tracking_number}}'. Incluye una estimación de la fecha de entrega y un enlace para rastrear el paquete en tiempo real. Si el pedido está retrasado, ofrece una disculpa y una breve explicación."`
2. **Prompt de Devolución de Producto:** Crear un prompt para guiar al cliente en el proceso de devolución.
   - **Desafío:** que el modelo distinga entre productos que **pueden** devolverse y los que **no** (ej: productos perecederos, productos de higiene). La respuesta debe ser clara y empática, incluso si la devolución no es posible.

Solución: [`fase_3_prompts.md`](./fase_3_prompts.md)

---

## 3. Forma de Entrega

Link del repositorio de **GitHub** que contiene la respuesta a las tres fases.
- Para las **primeras dos fases** (respuestas más textuales), se debe usar formato **Markdown** para presentar la respuesta.
- Para la **tercera fase**, el repositorio debe contener la **estructura necesaria para ejecutar el código** y obtener respuestas ante los prompts.

---

## 4. Rúbrica de Evaluación del Taller (5 Puntos)

### 4.1. Selección y Justificación del Modelo de IA (2 puntos)
- **2 pts:** Selecciona un modelo adecuado y presenta una justificación completa, considerando arquitectura, costo, escalabilidad y facilidad de integración. Demuestra profundo entendimiento del caso.
- **1 pt:** Selecciona un modelo pero la justificación es superficial o incompleta. Se limita a un solo factor o no conecta la elección con los requisitos del negocio.
- **0 pts:** No selecciona un modelo o la justificación es irrelevante e incorrecta.

### 4.2. Evaluación de Fortalezas, Limitaciones y Riesgos Éticos (2 puntos)
- **2 pts:** Identifica de manera crítica y exhaustiva fortalezas, limitaciones y **especialmente los riesgos éticos**. Muestra pensamiento proactivo sobre sesgos, privacidad de datos e impacto laboral.
- **1 pt:** Identifica algunas fortalezas y limitaciones, pero el análisis de riesgos éticos es básico o ausente.
- **0 pts:** No realiza la evaluación crítica o los puntos son incorrectos.

### 4.3. Aplicación de Principios de Ingeniería de Prompts (1 punto)
- **1 pt:** Crea prompts claros y efectivos. Demuestra buen entendimiento de cómo la estructura, el rol del modelo y el contexto influyen en la calidad de la respuesta.
- **0 pts:** Prompts inefectivos o ejercicio incompleto.

---

📎 Volver al [`README.md`](./README.md)
