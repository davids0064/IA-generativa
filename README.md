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

---

## Estructura del repositorio

```
IA-generativa/
├── README.md                       # Índice principal (este archivo)
├── context.md                      # Caso de uso + estructura del taller
├── fase_1_seleccion_modelo.md      # Solución Fase 1
├── fase_2_evaluacion.md            # Solución Fase 2
└── fase_3_prompts.md               # Solución Fase 3 (prompts + código)
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

