# Fase 1 — Selección y Justificación del Modelo de IA

📎 Navegación: [`README.md`](./README.md) · [`context.md`](./context.md) · **Fase 1** · [`Fase 2`](./fase_2_evaluacion.md) · [`Fase 3`](./fase_3_prompts.md)

---

## ¿Qué tipo de modelo de IA generativa es el más adecuado?
*(ej: un modelo de lenguaje grande (LLM) como GPT-4, un modelo de lenguaje pequeño afinado (Fine-tuned LLM), o una solución híbrida).*

Para resolver el cuello de botella en la atención al cliente de **EcoMarket**, utilizaremos una **solución híbrida**, donde:
* **80% de las consultas repetitivas (Autopilot):** Serán atendidas automáticamente por un modelo SLM/LLM ligero, eficiente y de baja latencia (ej. GPT-4o-mini, Claude 3 Haiku o Llama 3 8B) implementando la arquitectura **RAG (Retrieval-Augmented Generation)**.
* **20% de las consultas complejas (Copiloto Humano):** Serán derivadas a los agentes de soporte humanos, asistidos en segundo plano por un modelo de lenguaje avanzado de alto razonamiento (ej. DeepSeek-R1 o GPT-4o) que generará borradores de respuesta empáticos y resumirá el historial del caso para que el agente responda en pocos segundos.

---

## ¿Por qué este modelo y no otro?
*Consideren la necesidad de precisión para temas de pedidos vs. la necesidad de fluidez para respuestas a preguntas generales.*

### RAG vs. Fine-Tuning (Ajuste Fino):
* **Por qué NO solo Fine-Tuning:** Entrenar o afinar un modelo (*Fine-Tuning*) codifica la información dentro de sus pesos numéricos (*parametric memory*). Si un cliente pregunta *"¿Dónde está mi paquete del pedido #1234?"*, un modelo afinado **alucinará** (inventará un estado falso) o dará información obsoleta, ya que esa orden de compra se pudo haber generado hace 5 minutos y no existía en su conjunto de entrenamiento.
* **Por qué RAG:** RAG funciona como una "evaluación a libro abierto". El modelo no memoriza los datos cambiantes de EcoMarket; cuando llega una consulta, busca los datos exactos y en tiempo real en las bases de datos de la empresa y genera una respuesta basada únicamente en esa información fresca y verificada.

### Precisión vs. Fluidez:
* **Para el 80% (Pedidos, Devoluciones, Catálogo):** Se requiere **100% de precisión de datos factuales**. La arquitectura RAG restringe al modelo para que no invente reglas; si la política de devolución exige 30 días, el sistema garantizará que nunca indique 60 días.
* **Para el 20% (Quejas, Reclamos y Empatía):** Un bot 100% automatizado corre el riesgo de sonar frío, robótico e insensible ante un cliente frustrado. Usar un LLM potente en modo "Copiloto Humano" permite redactar propuestas de respuesta con tono cálido, humano y comprensivo, dejando la decisión final y el toque personalizado en manos del agente de soporte.

---

## ¿Cuál sería la arquitectura propuesta?
*¿El modelo se integraría con la base de datos de EcoMarket (catálogo de productos, información de envíos)? ¿Sería un modelo de propósito general o se afinaría con datos de la empresa?*

### Integración con Sistemas Core:
El sistema **DEBE integrarse obligatoriamente** mediante APIs y conectores con:
1. **ERP / CRM / Sistema de Logística:** Para consultar en tiempo real el estado de compras, guia de rastreo, historial del cliente y stock en inventario.
2. **Base de Datos Vectorial (Knowledge Base):** Base de conocimientos que contiene las políticas de sostenibilidad de EcoMarket, manuales de uso de productos ecológicos, FAQs y términos de servicio procesados e indexados.

### Flujo de Atención en 4 Pasos:
1. **Entrada y Clasificación:** El cliente escribe a través de WhatsApp, chat web o correo electrónico. Un agente enrutador (*Router Agent*) analiza la intención del mensaje, la categoría del problema y la carga emocional/sentimiento.
2. **Ruta A (80% Repetitivo - Autopilot):** Si el cliente consulta *"¿Dónde está mi pedido #550?"*, el bot consulta la API del sistema de envíos, obtiene la ubicación actual (*"En tránsito, llega mañana"*) y redacta una respuesta amigable al instante.
3. **Ruta B (20% Complejo - Handoff a Humano):** Si el *Router* detecta insatisfacción alta, reclamos por productos dañados o situaciones fuera de protocolo, el bot **no responde de forma autónoma**, sino que transfiere la conversación al panel del equipo humano.
4. **Asistencia Copiloto:** El LLM avanzado sintetiza el problema del cliente, analiza el historial de compras y redacta una sugerencia de respuesta empática que el agente humano valida, edita si es necesario y envía con un solo clic.

---

## Justificación
*Argumentos basados en criterios como costo, escalabilidad, facilidad de integración y la calidad de la respuesta esperada.*

* **Costos:**
  * Utilizar modelos pequeños y optimizados (API de pago por token accesible como GPT-4o-mini o modelos *open-source* como Llama 3) para el 80% de los mensajes reduce los costos operativos de infraestructura en más de un 80% frente al uso indiscriminado de modelos gigantes para todo el volumen.
  * Elimina el costo económico y computacional recurrente de re-entrenar (*Fine-Tuning*) el modelo cada vez que cambia el catálogo de productos o la logística de envíos.
* **Escalabilidad:**
  * La arquitectura RAG absorbe picos masivos de demanda (HotSale, Black Friday, campañas navideñas) sin degradación del servicio ni sobrecarga del personal, respondiendo en cuestión de segundos en lugar de las 24 horas actuales.
* **Facilidad de Integración:**
  * Al emplear modelos de propósito general acoplados con RAG, la implementación se realiza rápidamente utilizando orquestadores como LangChain, LlamaIndex o n8n, conectando las APIs existentes de EcoMarket mediante *webhooks*.
* **Calidad y Reducción de Alucinaciones:**
  * La arquitectura RAG limita explícitamente el rango de respuesta del LLM a los fragmentos e información recuperados de los sistemas de EcoMarket. Si el dato no existe, la regla del sistema indica responder: *"No dispongo de esa información en este momento, te transferiré con un asesor humano"*, protegiendo la reputación y confianza de la marca.

---

📎 Continuar con [`Fase 2 — Evaluación de Fortalezas, Limitaciones y Riesgos Éticos`](./fase_2_evaluacion.md)
