"""Cliente del modelo de lenguaje.

Usa la API compatible con OpenAI que expone Ollama en local, de modo que el
mismo código sirve para un modelo open-source o para un proveedor en la nube
cambiando únicamente las variables de entorno.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
MODELO = os.getenv("LLM_MODEL", "llama3.1:8b")
TEMPERATURA = float(os.getenv("LLM_TEMPERATURE", "0.2"))

_cliente = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def completar(mensajes: list[dict], formato_json: bool = False) -> str:
    """Envía la conversación al modelo y devuelve el texto de la respuesta.

    `formato_json` activa el modo de salida estructurada, usado por el prompt
    mejorado para garantizar un objeto JSON parseable.
    """
    parametros = {
        "model": MODELO,
        "messages": mensajes,
        "temperature": TEMPERATURA,
    }
    if formato_json:
        parametros["response_format"] = {"type": "json_object"}

    respuesta = _cliente.chat.completions.create(**parametros)
    return respuesta.choices[0].message.content.strip()
