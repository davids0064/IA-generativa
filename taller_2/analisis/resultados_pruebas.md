# Resultados de las Pruebas del Agente con RAG

📎 Navegación: [`README general`](../../README.md) · [`Taller 2`](../README.md) · [`Fase 1`](./fase_1_seleccion_componentes.md) · [`Fase 2`](./fase_2_creacion_base_conocimiento.md) · [`Fase 3`](./fase_3_integracion_rag.md) · **Pruebas**

---

Este documento registra la ejecución de los dos agentes del Taller 2 en modo `rag`
sobre cuatro casos representativos. Cada caso se contrasta con lo que el manual de
políticas de EcoMarket exige (resultado esperado), se evalúa por separado la
**recuperación** (¿llegaron al modelo los fragmentos con la regla correcta?) y la
**generación** (¿el modelo aplicó bien esa regla?), y se adjunta la captura de la
ejecución real.

## Contenido

- [1. Entorno de ejecución](#1-entorno-de-ejecución)
- [2. Resumen de resultados](#2-resumen-de-resultados)
- [3. Detalle por caso](#3-detalle-por-caso)
- [4. Análisis](#4-análisis)
- [5. Mejoras propuestas](#5-mejoras-propuestas)

---

## 1. Entorno de ejecución

| Elemento | Valor |
| :--- | :--- |
| Fecha de ejecución | 2026-09-29 (las ventanas de devolución se calculan contra esta fecha) |
| LLM | `qwen2.5:3b` (cuantizado a 4 bits), servido por Ollama en Docker, temperatura 0.2 |
| Embeddings | `bge-m3`, servido por el mismo Ollama |
| Base vectorial | Servidor ChromaDB `1.5.9` (Docker), 42 chunks cargados una sola vez con el servicio `indexer` |
| Hardware | Portátil macOS Intel, sin GPU dedicada (inferencia en CPU) |
| Recuperación | Top-4 por similitud; en devoluciones, secciones del manual por metadatos + ficha por `sku` + top-2 por similitud |

Los comandos se ejecutaron desde `taller_2/` tal como se documenta en el
[README del Taller 2](../README.md#puesta-en-marcha).

---

## 2. Resumen de resultados

| # | Agente | Caso | Recuperación | Generación | Veredicto |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 1 | `main.py` | Devolver un jabón ya abierto | Correcta | Correcta | Acierto |
| 2 | `main.py` | ¿Reembolsan el envío de un pedido retrasado? | Faltó la sección 2 del manual | No inventa; escala | Fallo seguro |
| 3 | `main_devolucion.py` | Panel solar defectuoso a los 22 días | Correcta | Rechaza una garantía vigente; escala | Fallo seguro |
| 4 | `main_devolucion.py` | Cepillo de dientes por cambio de opinión | Correcta | Correcta | Acierto |

**Balance:** 2 de 4 casos resueltos correctamente. En los otros 2 el agente no
entregó información falsa como verdadera: marcó `answer_grounded: false` y
`escalate_to_human: true`, de modo que el caso llegaría a un asesor humano. Es el
comportamiento de respaldo diseñado en el Taller 1 (Fase 2, mitigación de
alucinaciones), pero el cliente no recibe la respuesta correcta en el primer contacto.

---

## 3. Detalle por caso

### Caso 1 — Devolver un jabón ya abierto (sin pedido)

```bash
uv run python -m src.main --modo rag --consulta "¿Puedo devolver un jabón que ya abrí?"
```

| | |
| :--- | :--- |
| **Esperado** | Rechazar la devolución: los productos de higiene personal están excluidos del derecho de retracto (manual, sección 4.1). Ofrecer la garantía de 30 días si el producto llegó dañado (sección 4.2). |
| **Fragmentos recuperados** | [1] FAQ: ¿puedo devolver un producto que ya abrí? · [2] Política 4.1 Derecho de retracto · [3] FAQ: ¿por qué no puedo devolver productos de higiene? · [4] Ficha del jabón artesanal de avena |
| **Respuesta** | `order_found: null`, `answer_grounded: true`, `sources_used: [2, 3]`, `escalate_to_human: false`. Rechaza por ser de higiene personal y ofrece la garantía de 30 días. |
| **Veredicto** | **Acierto.** Sin número de pedido, el agente identifica el producto en el catálogo, aplica la exclusión correcta, cita la política y la FAQ que la sustentan y propone una alternativa. |

<img width="1235" height="414" alt="Caso 1: consulta sobre devolver un jabón abierto" src="https://github.com/user-attachments/assets/d7582ff7-9d86-40ca-b2da-95bcec76137e" />

### Caso 2 — Reembolso del envío por retraso (pedido ECO-2024-0004)

```bash
uv run python -m src.main --modo rag --tracking ECO-2024-0004 --consulta "¿Me devuelven el envío por el retraso?"
```

| | |
| :--- | :--- |
| **Esperado** | El pedido está `Retrasado` (fecha estimada 2026-08-27, retenido en aduana). La sección 2 del manual indica que EcoMarket reembolsa el costo del envío cuando el retraso supera 5 días hábiles, como es el caso. Respuesta esperada: confirmar el reembolso del envío e informar la nueva fecha estimada (2026-09-11). |
| **Fragmentos recuperados** | [1] Ficha del kit de shampoo sólido · [2] Política 4.1 Derecho de retracto · [3] FAQ: productos de higiene · [4] Política 4.3 Reembolsos. **No se recuperó la sección 2 (Retrasos e incidencias)**, que contiene la regla. |
| **Respuesta** | `order_found: true`, `status: Retrasado`, `answer_grounded: false`, `escalate_to_human: true`. Responde sobre el derecho de retracto de productos de higiene, que no es lo que se preguntó. |
| **Veredicto** | **Fallo seguro.** El error está en la **recuperación**: la búsqueda se enriquece con el producto y la categoría del pedido (higiene personal), y ese sesgo desplazó la política de retrasos fuera del top-4. El modelo reconoce que el contexto no basta (`answer_grounded: false`) y escala, pero su mensaje al cliente mezcla una política irrelevante. |

<img width="1236" height="605" alt="Caso 2: consulta sobre reembolso del envío de un pedido retrasado" src="https://github.com/user-attachments/assets/d7829e60-1b13-4df2-841c-690a0d562aca" />

> En la primera ronda de pruebas (tabla de resultados de la
> [Fase 3](./fase_3_integracion_rag.md#resultados-observados-qwen253b--bge-m3)) este mismo
> caso sí recuperó la sección 2 y confirmó el reembolso. La diferencia muestra que la
> recuperación por similitud pura es sensible a la redacción y al contexto añadido a
> la búsqueda; ver [mejora 1](#5-mejoras-propuestas).

### Caso 3 — Panel solar defectuoso a los 22 días (pedido ECO-2024-0008)

```bash
uv run python -m src.main_devolucion --modo rag --tracking ECO-2024-0008 --motivo producto_defectuoso
```

| | |
| :--- | :--- |
| **Esperado** | Producto de Tecnología entregado hace 22 días calendario. Motivo `producto_defectuoso` → vía garantía (sección 4.2): ventana de 30 días calendario, vigente. Como no es perecedero ni de higiene, EcoMarket recoge el producto. Resultado esperado: `return_eligible: true`, `return_method: garantia`, `requires_physical_return: true`, mencionando además la garantía de 12 meses del fabricante (sección 5). |
| **Fragmentos recuperados** | [1] Política 4.2 Garantía · [2] Política 5 Garantía de tecnología · [3] Política 4.3 Reembolsos · [4] Ficha del panel solar · [5] Ficha del cargador solar. Las tres secciones que deciden el caso llegaron por filtro de metadatos. |
| **Respuesta** | `return_eligible: false`, `rejection_reason: motivo_requiere_revision`, `answer_grounded: false`, `sources_used: [2, 4, 5]`, `escalate_to_human: true`. Afirma que la garantía "no aplica para EcoMarket" y remite al cliente al fabricante. |
| **Veredicto** | **Fallo seguro.** La **recuperación fue correcta**: la regla estaba en el fragmento [1]. El error es de **razonamiento del modelo**: no citó [1], confundió la garantía de EcoMarket (30 días) con la del fabricante (12 meses) y concluyó lo contrario de la política. Escaló a un asesor, que corregiría la decisión. |

<img width="1105" height="815" alt="Caso 3: devolución de un panel solar defectuoso" src="https://github.com/user-attachments/assets/dd1d9584-b5ed-43fd-9a06-0a52bf4dd294" />

### Caso 4 — Cepillo de dientes por cambio de opinión (pedido ECO-2024-0001)

```bash
uv run python -m src.main_devolucion --modo rag --tracking ECO-2024-0001 --motivo cambio_de_opinion
```

| | |
| :--- | :--- |
| **Esperado** | Producto de higiene personal. Motivo `cambio_de_opinion` → vía retracto, que excluye la higiene personal (sección 4.1). Rechazar con `categoria_excluida_de_retracto` y ofrecer la garantía como alternativa: con 30 días calendario desde la entrega, sigue vigente ese día (sección 4.2). |
| **Fragmentos recuperados** | [1] Política 4.1 Derecho de retracto · [2] Política 4.2 Garantía · [3] Política 4.3 Reembolsos · [4] Ficha del cepillo de bambú · [5] FAQ: productos de higiene |
| **Respuesta** | `return_eligible: false`, `rejection_reason: categoria_excluida_de_retracto`, `answer_grounded: true`, `sources_used: [1, 2]`. Rechaza con empatía y ofrece la garantía de 30 días. |
| **Veredicto** | **Acierto**, con dos desviaciones menores: marca `escalate_to_human: true` sin que se cumpla ninguna condición de escalamiento, y el `reasoning` repite literalmente una frase del ejemplo few-shot ("[3] no es relevante"). |

<img width="1105" height="800" alt="Caso 4: devolución de un cepillo de dientes por cambio de opinión" src="https://github.com/user-attachments/assets/150fc59f-ded4-4366-aff6-cce5167b1a94" />

---

## 4. Análisis

**Recuperación.** Donde las secciones del manual se recuperan por **metadatos**
(agente de devoluciones, casos 3 y 4), la regla que decide el caso llegó siempre al
modelo. Donde se recupera solo por **similitud** (agente general, caso 2), una
consulta enriquecida con la categoría del producto desplazó la política pertinente.
Esto confirma la decisión de diseño de la Fase 3 de no dejar las reglas críticas a
merced del ranking semántico.

**Generación.** Con la regla correcta en el contexto, `qwen2.5:3b` acertó en el caso
de exclusión (caso 4) y falló en el caso que exigía combinar dos garantías (caso 3).
Es la limitación ya anticipada en las
[limitaciones y suposiciones](../README.md#limitaciones-y-suposiciones): un modelo de
3B parámetros recupera bien pero razona peor cuando varias políticas compiten.

**Seguridad.** Ninguna respuesta inventó plazos, precios ni políticas inexistentes.
En los dos fallos el modelo marcó la respuesta como no fundamentada y escaló a un
humano, que es la salvaguarda del enfoque *human-in-the-loop* del Taller 1.

**Trazabilidad.** Cada respuesta muestra los fragmentos recuperados y los que el
modelo citó (`sources_used`), lo que permitió localizar la causa de cada fallo
(recuperación en el caso 2, razonamiento en el caso 3) sin inspeccionar el prompt.

---

## 5. Mejoras propuestas

1. **Secciones obligatorias también en el agente general.** Aplicar a `main.py` el
   mismo filtro por metadatos del agente de devoluciones: si el pedido está
   `Retrasado` o en `Incidencia`, incluir siempre la sección 2 del manual. Corrige el
   caso 2 sin depender del modelo.
2. **Modelo de mayor capacidad.** Repetir los casos con `llama3.1:8b` o un modelo por
   API (`gpt-4o-mini`) cambiando solo `LLM_MODEL` en `.env`; el caso 3 es el indicador
   de si el modelo combina bien varias políticas.
3. **Validación determinista de la decisión.** Las ventanas y exclusiones son reglas
   fijas: el código puede verificar `return_eligible` contra los días y las banderas del
   pedido, y escalar cuando el modelo contradiga la regla recuperada.
4. **Evaluación automática.** Convertir estos cuatro casos (y el barrido
   `main_devolucion --todos`) en un conjunto de pruebas con resultado esperado, y medir
   la calidad de la recuperación y de la respuesta con métricas como las de RAGAS.

---

Volver al [`README del Taller 2`](../README.md)
