# Caso de Estudio: Optimización de la Atención al Cliente en EcoMarket

## Fase 1: Selección y Justificación del Modelo de IA

### ¿Qué tipo de modelo de IA generativa es el más adecuado?
*(ej: un modelo de lenguaje grande (LLM) como GPT-4, un modelo de lenguaje pequeño afinado (Fine-tuned LLM), o una solución híbrida).*

Para resolver el cuello de botella en la atención al cliente de **EcoMarket**, utilizaremos una **solución híbrida**, donde:
* **80% de las consultas repetitivas (Autopilot):** Serán atendidas automáticamente por un modelo SLM/LLM ligero, eficiente y de baja latencia (ej. GPT-4o-mini, Claude 3 Haiku o Llama 3 8B) implementando la arquitectura **RAG (Retrieval-Augmented Generation)**.
* **20% de las consultas complejas (Copiloto Humano):** Serán derivadas a los agentes de soporte humanos, asistidos en segundo plano por un modelo de lenguaje avanzado de alto razonamiento (ej. DeepSeek-R1 o GPT-4o) que generará borradores de respuesta empáticos y resumirá el historial del caso para que el agente responda en pocos segundos.

---

### ¿Por qué este modelo y no otro?
*Consideren la necesidad de precisión para temas de pedidos vs. la necesidad de fluidez para respuestas a preguntas generales.*

#### RAG vs. Fine-Tuning (Ajuste Fino):
* **Por qué NO solo Fine-Tuning:** Entrenar o afinar un modelo (*Fine-Tuning*) codifica la información dentro de sus pesos numéricos (*parametric memory*). Si un cliente pregunta *"¿Dónde está mi paquete del pedido #1234?"*, un modelo afinado **alucinará** (inventará un estado falso) o dará información obsoleta, ya que esa orden de compra se pudo haber generado hace 5 minutos y no existía en su conjunto de entrenamiento.
* **Por qué RAG:** RAG funciona como una "evaluación a libro abierto". El modelo no memoriza los datos cambiantes de EcoMarket; cuando llega una consulta, busca los datos exactos y en tiempo real en las bases de datos de la empresa y genera una respuesta basada únicamente en esa información fresca y verificada.

#### Precisión vs. Fluidez:
* **Para el 80% (Pedidos, Devoluciones, Catálogo):** Se requiere **100% de precisión de datos factuales**. La arquitectura RAG restringe al modelo para que no invente reglas; si la política de devolución exige 30 días, el sistema garantizará que nunca indique 60 días.
* **Para el 20% (Quejas, Reclamos y Empatía):** Un bot 100% automatizado corre el riesgo de sonar frío, robótico e insensible ante un cliente frustrado. Usar un LLM potente en modo "Copiloto Humano" permite redactar propuestas de respuesta con tono cálido, humano y comprensivo, dejando la decisión final y el toque personalizado en manos del agente de soporte.

---

### ¿Cuál sería la arquitectura propuesta?
*¿El modelo se integraría con la base de datos de EcoMarket (catálogo de productos, información de envíos)? ¿Sería un modelo de propósito general o se afinaría con datos de la empresa?*

#### Integración con Sistemas Core:
El sistema **DEBE integrarse obligatoriamente** mediante APIs y conectores con:
1. **ERP / CRM / Sistema de Logística:** Para consultar en tiempo real el estado de compras, guia de rastreo, historial del cliente y stock en inventario.
2. **Base de Datos Vectorial (Knowledge Base):** Base de conocimientos que contiene las políticas de sostenibilidad de EcoMarket, manuales de uso de productos ecológicos, FAQs y términos de servicio procesados e indexados.

#### Flujo de Atención en 4 Pasos:
1. **Entrada y Clasificación:** El cliente escribe a través de WhatsApp, chat web o correo electrónico. Un agente enrutador (*Router Agent*) analiza la intención del mensaje, la categoría del problema y la carga emocional/sentimiento.
2. **Ruta A (80% Repetitivo - Autopilot):** Si el cliente consulta *"¿Dónde está mi pedido #550?"*, el bot consulta la API del sistema de envíos, obtiene la ubicación actual (*"En tránsito, llega mañana"*) y redacta una respuesta amigable al instante.
3. **Ruta B (20% Complejo - Handoff a Humano):** Si el *Router* detecta insatisfacción alta, reclamos por productos dañados o situaciones fuera de protocolo, el bot **no responde de forma autónoma**, sino que transfiere la conversación al panel del equipo humano.
4. **Asistencia Copiloto:** El LLM avanzado sintetiza el problema del cliente, analiza el historial de compras y redacta una sugerencia de respuesta empática que el agente humano valida, edita si es necesario y envía con un solo clic.

---

### Justificación
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

## Fase 2: Evaluación de Fortalezas, Limitaciones y Riesgos Éticos

### Fortalezas
*¿Qué haría bien el modelo propuesto? (ej: reducción del tiempo de respuesta, disponibilidad 24/7, manejo del 80% de las consultas repetitivas).*

| Área | Impacto Directo en EcoMarket |
| :--- | :--- |
| **Reducción del SLA (Tiempo de Respuesta)** | Reduce el tiempo medio de respuesta de **24 horas a menos de 10 segundos** para el 80% de las consultas repetitivas. |
| **Disponibilidad y Escalabilidad 24/7** | Cobertura ininterrumpida los 365 días del año, capaz de absorber picos de tráfico sin saturar el sistema ni requerir contrataciones temporales. |
| **Precisión Factual mediante RAG** | Garantiza respuestas basadas en datos fidedignos y actualizados al segundo mediante la conexión directa con el ERP e inventario. |
| **Optimización de Costos Operativos** | Filtrar el volumen masivo reduce el costo por ticket y la carga cognitiva del personal, liberando presupuesto para capacitación. |
| **Consistencia en la Marca** | Comunicación estandarizada alineada con los valores de sostenibilidad y las políticas vigentes de EcoMarket. |

---

### Limitaciones
*¿Qué no podría hacer el modelo? (ej: no puede manejar el 20% de los casos complejos que requieren empatía, podría dar respuestas incorrectas si la información de la base de datos es errónea).*

* **Comprensión Contextual y Empatía Genuina:** Los modelos generativos simulan empatía mediante patrones de texto, pero carecen de juicio moral, sentido común, inteligencia emocional y comprensión profunda ante situaciones delicadas.
* **Dependencia Crítica de la Calidad de Datos (*Garbage In, Garbage Out*):** Si las bases de datos de EcoMarket, las guías de envío o las FAQs contienen errores o desactualizaciones, el sistema RAG entregará respuestas erróneas con total seguridad aparente.
* **Manejo de Casos Extremo (*Edge Cases*):** Escenarios no documentados previamente en las bases de datos (ej. paquetes extraviados por desastres naturales o disputas legales de devolución) escapan a las capacidades del bot.
* **Dependencia y Latencia de Servicios Externos:** La estabilidad de la solución está sujeta a la disponibilidad de las APIs de terceros (proveedores de LLM, base de datos vectorial y servicios del ERP).

---

### Riesgos Éticos y Estrategias de Mitigación

#### 1. Alucinaciones
*El modelo podría inventar información sobre pedidos o productos.*
* **Riesgo:** Generación de información falsa sobre el estado de un envío, inventar descuentos o alterar las políticas de garantía de productos ecológicos.
* **Mitigación Técnica:**
  * **Grounding Estricto:** Configurar el *System Prompt* del modelo instruyéndole responder **únicamente** con el contexto explícito retornado por la arquitectura RAG.
  * **Ajuste de Temperatura:** Configurar el parámetro de temperatura entre `0.0` y `0.2` para minimizar la creatividad y priorizar la precisión determinista.

#### 2. Sesgo (Bias)
*El modelo podría reflejar sesgos de los datos de entrenamiento, ofreciendo respuestas preferenciales a ciertos grupos de clientes.*
* **Riesgo:** Reflejar sesgos regionales, de clase o dialecto presentes en los datos con los que el LLM fue preentrenado, resultando en un tono inadvertidamente frío o condescendiente.
* **Mitigación Técnica:**
  * **Auditorías de Prompts y Red-Teaming:** Realizar pruebas periódicas utilizando diversos modismos, niveles socioeconómicos y variaciones dialectales para evaluar la equidad del trato.
  * **Guías de Estilo Neutras:** Establecer pautas rígidas de tono institucional en las instrucciones del sistema para garantizar neutralidad y respeto equitativo.

#### 3. Privacidad de Datos (PII - Information Handling)
*¿Cómo se manejaría la información sensible de los clientes (direcciones, historial de compras) si se utiliza para afinar el modelo o como contexto en los prompts?*
* **Riesgo:** Exposición involuntaria de datos personales sensibles (nombres, direcciones, tarjetas de crédito, números de identificación) al enviarlos en las solicitudes a las APIs de los modelos generativos.
* **Mitigación Técnica:**
  * **Anonimización Previa (Data Masking):** Incorporar un filtro de inspección previo que identifique y enmascare datos PII (ej. reescribir *"Vivo en Av. Siempre Viva 123"* como `[DIRECCIÓN_PROTEGIDA]`) antes de enviar el texto al modelo externo.
  * **Contratos Enterprise / Zero Data Retention (ZDR):** Suscribir acuerdos de nivel empresarial (ej. Azure OpenAI o GCP Vertex AI) donde los proveedores garantizan legalmente que los datos del cliente no se almacenan ni se utilizan para entrenar modelos públicos.

#### 4. Impacto Laboral
*¿Qué pasaría con los agentes de servicio al cliente? ¿El objetivo es reemplazarlos o empoderarlos?*
* **Riesgo:** Incertidumbre laboral, resistencia al cambio o temor a la sustitución de puestos de trabajo por parte del equipo de soporte humano.
* **Estrategia y Posicionamiento:**
  * **Filosofía "Human-in-the-Loop" (Empoderamiento, no Reemplazo):** La IA asume las tareas monótonas, repetitivas y desgastantes (responder cientos de veces al día *"¿dónde está mi paquete?"*).
  * **Evolución del Rol:** Transición del personal de soporte hacia el rol de **Especialistas en Experiencia del Cliente**, enfocados en resolver con alta empatía el 20% de casos complejos, tomar decisiones emocionales o de negocio y supervisar el desempeño de la IA.