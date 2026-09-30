# Taller Práctico #1 — Modelo, riesgos e ingeniería de prompts

> **Versión 1 de la solución.** El agente de EcoMarket responde con prompts diseñados a mano
> y los datos del pedido inyectados como contexto. Aún no tiene base de conocimiento
> vectorial; esa evolución está en el [Taller 2](../taller_2/README.md).

Volver al [README general](../README.md)

---

## Navegación

| Fase | Descripción | Documento |
| :---: | :--- | :--- |
| **1** | Selección y justificación del modelo de IA | [`fase_1_seleccion_modelo.md`](./analisis/fase_1_seleccion_modelo.md) |
| **2** | Evaluación de fortalezas, limitaciones y riesgos éticos | [`fase_2_evaluacion.md`](./analisis/fase_2_evaluacion.md) |
| **3** | Aplicación de la ingeniería de prompts (código ejecutable) | [`fase_3_prompts.md`](./analisis/fase_3_prompts.md) |

- [Enunciado del taller](#1-caso-de-estudio-optimización-de-la-atención-al-cliente-en-una-empresa-de-e-commerce)
- [Estructura de esta versión](#estructura-de-esta-versión)
- [Puesta en marcha y pruebas](#puesta-en-marcha-y-pruebas)

---

## Estructura de esta versión

```
taller_1/
├── README.md                   # Este archivo: enunciado, navegación y ejecución
├── analisis/                   # Solución documentada de cada fase
│   ├── fase_1_seleccion_modelo.md
│   ├── fase_2_evaluacion.md
│   └── fase_3_prompts.md       # Prompts, ejemplos de ejecución y guía del código
├── data/dataset.json           # Pedidos (base de datos simulada)
├── src/
│   ├── main.py                 # Ejercicio 1: prompt básico vs. mejorado
│   ├── main_devolucion.py      # Ejercicio 2: devoluciones
│   ├── prompts.py · prompts_devolucion.py
│   └── llm.py · db.py          # Cliente del LLM y acceso a pedidos
├── requirements.txt · .env.example
└── Dockerfile · docker-compose.yml
```

Todos los comandos de este documento se ejecutan **desde la carpeta `taller_1/`**.

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

➡️ Solución: [`fase_1_seleccion_modelo.md`](./analisis/fase_1_seleccion_modelo.md)

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

Solución: [`fase_2_evaluacion.md`](./analisis/fase_2_evaluacion.md)

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

Solución: [`fase_3_prompts.md`](./analisis/fase_3_prompts.md)

---

## Puesta en marcha y pruebas

> Guía rápida con capturas de una ejecución real. El paso a paso completo (comandos, variables de entorno, Docker Compose) está en el [punto 3 — Código ejecutable de la Fase 3](./analisis/fase_3_prompts.md#3-código-ejecutable).

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

`python -m src.main --tracking <tracking>` — muestra la diferencia entre el **prompt básico** (sin rol ni contexto) y el **prompt mejorado** (RAG + reglas + JSON estructurado). Detalle en la [sección 1](./analisis/fase_3_prompts.md#1-prompt-de-solicitud-de-pedido).

<img width="822" height="674" alt="Comparación entre el prompt básico y el prompt mejorado" src="https://github.com/user-attachments/assets/a62138d3-8503-4dd4-9398-4ba9d44fe22f" />

#### 3.3. Ejercicio 2 — Devolución de un producto

`python -m src.main_devolucion --listar` — atributos relevantes para decidir la elegibilidad (categoría, perecedero, higiene, fecha de entrega). Detalle en la [sección 2](./analisis/fase_3_prompts.md#2-prompt-de-devolución-de-producto).

<img width="878" height="284" alt="Atributos relevantes para evaluar una devolución" src="https://github.com/user-attachments/assets/cf074621-69e2-4659-a141-75d75a871af1" />

`python -m src.main_devolucion --tracking <tracking> --motivo <motivo>` — evalúa la solicitud contra la política de devoluciones y responde con el JSON estructurado.

<img width="1068" height="774" alt="Prueba de solicitud de devolución de un producto" src="https://github.com/user-attachments/assets/d74101a7-a6c4-49af-a245-d117cba96b78" />

---

📎 Volver al [README general](../README.md) · Siguiente versión: [Taller 2 — Sistema RAG](../taller_2/README.md)
