"""Acceso a la base de datos simulada de pedidos de EcoMarket.

En producción esta capa sería un cliente HTTP contra la API del ERP/OMS; aquí
lee el archivo `data/dataset.json` y expone la misma interfaz de búsqueda.
"""

import json
from pathlib import Path

RUTA_DATASET = Path(__file__).resolve().parent.parent / "data" / "dataset.json"

# Cada ejercicio inyecta en el prompt solo los campos que necesita: el registro
# completo mezcla datos logísticos con atributos comerciales del producto y esa
# información de más degrada la precisión del modelo.
CAMPOS_PEDIDO = (
    "tracking_number",
    "customer",
    "product",
    "quantity",
    "order_date",
    "estimated_delivery_date",
    "status",
    "current_location",
    "carrier",
    "tracking_url",
    "notes",
)

CAMPOS_DEVOLUCION = (
    "tracking_number",
    "customer",
    "product",
    "product_category",
    "is_perishable",
    "is_hygiene_item",
    "quantity",
    "order_date",
    "estimated_delivery_date",
    "delivered_date",
    "status",
    "notes",
)


def cargar_pedidos() -> list[dict]:
    """Devuelve todos los pedidos del dataset."""
    with RUTA_DATASET.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def buscar_pedido(tracking_number: str) -> dict | None:
    """Recupera un pedido por su número de seguimiento.

    La comparación ignora mayúsculas y espacios sobrantes para tolerar la
    forma en que el cliente escribe el número en el chat.
    """
    buscado = tracking_number.strip().upper()
    for pedido in cargar_pedidos():
        if pedido["tracking_number"].upper() == buscado:
            return pedido
    return None


def formatear_para_prompt(pedido: dict | None, campos: tuple[str, ...] | None = None) -> str:
    """Serializa el registro tal como se inyecta en <datos_pedido>.

    `campos` limita la salida a los atributos relevantes para el ejercicio
    (ver CAMPOS_PEDIDO y CAMPOS_DEVOLUCION). Devuelve cadena vacía cuando no
    hay pedido, que es la señal que los prompts interpretan como "pedido no
    encontrado".
    """
    if pedido is None:
        return ""
    if campos is not None:
        pedido = {clave: pedido[clave] for clave in campos if clave in pedido}
    return json.dumps(pedido, ensure_ascii=False, indent=2)
