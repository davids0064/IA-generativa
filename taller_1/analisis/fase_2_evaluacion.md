# Fase 2 — Evaluación de Fortalezas, Limitaciones y Riesgos Éticos

📎 Navegación: [`README general`](../../README.md) · [`Taller 1`](../README.md) · [`Fase 1`](./fase_1_seleccion_modelo.md) · **Fase 2** · [`Fase 3`](./fase_3_prompts.md)

---

## Fortalezas
*¿Qué haría bien el modelo propuesto? (ej: reducción del tiempo de respuesta, disponibilidad 24/7, manejo del 80% de las consultas repetitivas).*

| Área | Impacto Directo en EcoMarket |
| :--- | :--- |
| **Reducción del SLA (Tiempo de Respuesta)** | Reduce el tiempo medio de respuesta de **24 horas a menos de 10 segundos** para el 80% de las consultas repetitivas. |
| **Disponibilidad y Escalabilidad 24/7** | Cobertura ininterrumpida los 365 días del año, capaz de absorber picos de tráfico sin saturar el sistema ni requerir contrataciones temporales. |
| **Precisión Factual mediante RAG** | Garantiza respuestas basadas en datos fidedignos y actualizados al segundo mediante la conexión directa con el ERP e inventario. |
| **Optimización de Costos Operativos** | Filtrar el volumen masivo reduce el costo por ticket y la carga cognitiva del personal, liberando presupuesto para capacitación. |
| **Consistencia en la Marca** | Comunicación estandarizada alineada con los valores de sostenibilidad y las políticas vigentes de EcoMarket. |

---

## Limitaciones
*¿Qué no podría hacer el modelo? (ej: no puede manejar el 20% de los casos complejos que requieren empatía, podría dar respuestas incorrectas si la información de la base de datos es errónea).*

* **Comprensión Contextual y Empatía Genuina:** Los modelos generativos simulan empatía mediante patrones de texto, pero carecen de juicio moral, sentido común, inteligencia emocional y comprensión profunda ante situaciones delicadas.
* **Dependencia Crítica de la Calidad de Datos (*Garbage In, Garbage Out*):** Si las bases de datos de EcoMarket, las guías de envío o las FAQs contienen errores o desactualizaciones, el sistema RAG entregará respuestas erróneas con total seguridad aparente.
* **Manejo de Casos Extremo (*Edge Cases*):** Escenarios no documentados previamente en las bases de datos (ej. paquetes extraviados por desastres naturales o disputas legales de devolución) escapan a las capacidades del bot.
* **Dependencia y Latencia de Servicios Externos:** La estabilidad de la solución está sujeta a la disponibilidad de las APIs de terceros (proveedores de LLM, base de datos vectorial y servicios del ERP).

---

## Riesgos Éticos y Estrategias de Mitigación

### 1. Alucinaciones
*El modelo podría inventar información sobre pedidos o productos.*
* **Riesgo:** Generación de información falsa sobre el estado de un envío, inventar descuentos o alterar las políticas de garantía de productos ecológicos.
* **Mitigación Técnica:**
  * **Grounding Estricto:** Configurar el *System Prompt* del modelo instruyéndole responder **únicamente** con el contexto explícito retornado por la arquitectura RAG.
  * **Ajuste de Temperatura:** Configurar el parámetro de temperatura entre `0.0` y `0.2` para minimizar la creatividad y priorizar la precisión determinista.

### 2. Sesgo (Bias)
*El modelo podría reflejar sesgos de los datos de entrenamiento, ofreciendo respuestas preferenciales a ciertos grupos de clientes.*
* **Riesgo:** Reflejar sesgos regionales, de clase o dialecto presentes en los datos con los que el LLM fue preentrenado, resultando en un tono inadvertidamente frío o condescendiente.
* **Mitigación Técnica:**
  * **Auditorías de Prompts y Red-Teaming:** Realizar pruebas periódicas utilizando diversos modismos, niveles socioeconómicos y variaciones dialectales para evaluar la equidad del trato.
  * **Guías de Estilo Neutras:** Establecer pautas rígidas de tono institucional en las instrucciones del sistema para garantizar neutralidad y respeto equitativo.

### 3. Privacidad de Datos (PII - Information Handling)
*¿Cómo se manejaría la información sensible de los clientes (direcciones, historial de compras) si se utiliza para afinar el modelo o como contexto en los prompts?*
* **Riesgo:** Exposición involuntaria de datos personales sensibles (nombres, direcciones, tarjetas de crédito, números de identificación) al enviarlos en las solicitudes a las APIs de los modelos generativos.
* **Mitigación Técnica:**
  * **Anonimización Previa (Data Masking):** Incorporar un filtro de inspección previo que identifique y enmascare datos PII (ej. reescribir *"Vivo en Av. Siempre Viva 123"* como `[DIRECCIÓN_PROTEGIDA]`) antes de enviar el texto al modelo externo.
  * **Contratos Enterprise / Zero Data Retention (ZDR):** Suscribir acuerdos de nivel empresarial (ej. Azure OpenAI o GCP Vertex AI) donde los proveedores garantizan legalmente que los datos del cliente no se almacenan ni se utilizan para entrenar modelos públicos.

### 4. Impacto Laboral
*¿Qué pasaría con los agentes de servicio al cliente? ¿El objetivo es reemplazarlos o empoderarlos?*
* **Riesgo:** Incertidumbre laboral, resistencia al cambio o temor a la sustitución de puestos de trabajo por parte del equipo de soporte humano.
* **Estrategia y Posicionamiento:**
  * **Filosofía "Human-in-the-Loop" (Empoderamiento, no Reemplazo):** La IA asume las tareas monótonas, repetitivas y desgastantes (responder cientos de veces al día *"¿dónde está mi paquete?"*).
  * **Evolución del Rol:** Transición del personal de soporte hacia el rol de **Especialistas en Experiencia del Cliente**, enfocados en resolver con alta empatía el 20% de casos complejos, tomar decisiones emocionales o de negocio y supervisar el desempeño de la IA.

---

📎 Continuar con [`Fase 3 — Aplicación de la Ingeniería de Prompts`](./fase_3_prompts.md)
