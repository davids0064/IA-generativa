"""Sistemas externos simulados: órdenes de devolución (RMA), transportadora y mesa de ayuda.

En producción estas funciones serían clientes HTTP contra el OMS de EcoMarket,
la API de la transportadora y la herramienta de tickets. Aquí persisten en
archivos JSON dentro de `DATOS_OPERACION_DIR` (por defecto `data/`):

    devoluciones.json   registro de RMAs
    tickets.json        casos escalados a un asesor
    etiquetas/*.pdf     etiquetas de devolución generadas

La escritura es atómica (archivo temporal + `os.replace`) y está protegida con
un candado, porque la interfaz web puede atender varias sesiones a la vez.
"""

import hashlib
import json
import os
import tempfile
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A6, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

RAIZ = Path(__file__).resolve().parents[2]

# Destino de todas las devoluciones físicas (dirección ficticia).
CENTRO_DEVOLUCIONES = (
    "Centro de Devoluciones EcoMarket",
    "Calle 13 #68-45, Bodega 3",
    "Bogotá, Colombia",
)
TRANSPORTADORA_POR_DEFECTO = "EcoExpress"

_candado = threading.Lock()


class ServicioNoDisponible(Exception):
    """La API de la transportadora no respondió (simulado)."""


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------


def directorio_operacion() -> Path:
    """Se lee en cada llamada para que pruebas y evaluación usen un directorio aislado."""
    return Path(os.getenv("DATOS_OPERACION_DIR", RAIZ / "data"))


def _ruta(nombre: str) -> Path:
    return directorio_operacion() / nombre


def _leer(nombre: str) -> list[dict]:
    ruta = _ruta(nombre)
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def _escribir(nombre: str, registros: list[dict]) -> None:
    ruta = _ruta(nombre)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=ruta.parent, delete=False, suffix=".tmp"
    ) as temporal:
        json.dump(registros, temporal, ensure_ascii=False, indent=2)
    os.replace(temporal.name, ruta)


def _siguiente_id(prefijo: str, registros: list[dict], hoy: date, ancho: int) -> str:
    return f"{prefijo}-{hoy.year}-{len(registros) + 1:0{ancho}d}"


# ---------------------------------------------------------------------------
# Transportadora
# ---------------------------------------------------------------------------


def _falla_simulada(tracking_number: str) -> bool:
    """Activa la falla de la transportadora para demostrar el manejo de errores.

    `SIMULAR_FALLA_TRANSPORTADORA=true` la activa para todos los pedidos;
    `TRACKINGS_CON_FALLA=ECO-2024-0008,...` solo para los indicados.
    """
    if os.getenv("SIMULAR_FALLA_TRANSPORTADORA", "false").lower() in ("1", "true", "si", "sí"):
        return True
    con_falla = {t.strip().upper() for t in os.getenv("TRACKINGS_CON_FALLA", "").split(",") if t}
    return tracking_number.upper() in con_falla


def _dias_habiles_siguientes(desde: date, cantidad: int) -> list[date]:
    dias, cursor = [], desde
    while len(dias) < cantidad:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            dias.append(cursor)
    return dias


def _numero_guia(prefijo: str, rma_id: str, tracking: str) -> str:
    """Número de guía determinista (mismo RMA → misma guía), con formato de transportadora."""
    digitos = int(hashlib.sha256(f"{rma_id}|{tracking}".encode()).hexdigest(), 16) % 10**9
    return f"{prefijo}{digitos:09d}CO"


def _ciudad(pedido: dict) -> str:
    """Solo la ciudad del destino: la etiqueta no expone la dirección completa."""
    ubicacion = pedido.get("current_location") or ""
    return ubicacion.rsplit(",", 1)[-1].strip() if "," in ubicacion else "Colombia"


def _nombre_de_pila(pedido: dict) -> str:
    return (pedido.get("customer") or "Cliente").split()[0]


# ---------------------------------------------------------------------------
# RMA
# ---------------------------------------------------------------------------


def buscar_rma(tracking_number: str) -> dict | None:
    """Devuelve la RMA activa de un pedido, si existe (base de la idempotencia)."""
    for rma in _leer("devoluciones.json"):
        if rma["tracking_number"].upper() == tracking_number.upper():
            return rma
    return None


def crear_rma(
    pedido: dict, motivo: str, elegibilidad: dict, eligibility_token: str, hoy: date
) -> dict:
    """Registra la orden de devolución y, si hay recolección, genera guía y etiqueta.

    Lanza `ServicioNoDisponible` si la transportadora falla; en ese caso no se
    persiste nada, para que el reintento no deje registros a medias.
    """
    tracking = pedido["tracking_number"]
    fisica = bool(elegibilidad["requires_physical_return"])
    if fisica and _falla_simulada(tracking):
        raise ServicioNoDisponible(f"La transportadora no respondió para {tracking}")

    with _candado:
        registros = _leer("devoluciones.json")
        existente = next((r for r in registros if r["tracking_number"] == tracking), None)
        if existente:
            return existente

        rma_id = _siguiente_id("RMA", registros, hoy, 6)
        rma = {
            "rma": rma_id,
            "tracking_number": tracking,
            "customer_first_name": _nombre_de_pila(pedido),
            "product": pedido["product"],
            "reason": motivo,
            "return_method": elegibilidad["return_method"],
            "eligibility_token": eligibility_token,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "reference_date": hoy.isoformat(),
            "refund_timeframe": elegibilidad["refund_timeframe"],
        }
        if fisica:
            dias = _dias_habiles_siguientes(hoy, 3)
            carrier = pedido.get("carrier") or TRANSPORTADORA_POR_DEFECTO
            prefijo = "".join(p[0] for p in carrier.split() if p).upper()[:2] or "EX"
            rma.update(
                return_type="recoleccion",
                carrier=carrier,
                waybill_number=_numero_guia(prefijo, rma_id, tracking),
                pickup_window=f"{dias[0].isoformat()} a {dias[-1].isoformat()}",
                instructions=[
                    "Empaca el producto, idealmente en su empaque original.",
                    "Imprime la etiqueta y pégala en un lugar visible del paquete.",
                    "Ten el paquete listo en la ventana de recolección; la transportadora "
                    "pasa sin costo.",
                ],
            )
            rma["label_file"] = str(generar_pdf_etiqueta(rma, pedido))
        else:
            rma.update(
                return_type="sin_devolucion_fisica",
                carrier=None,
                waybill_number=None,
                pickup_window=None,
                label_file=None,
                instructions=[
                    "Responde el correo de confirmación con una foto clara del producto "
                    "y de su empaque.",
                    "Por bioseguridad no es necesario devolver el producto.",
                ],
            )
        registros.append(rma)
        _escribir("devoluciones.json", registros)
    return rma


def generar_pdf_etiqueta(rma: dict, pedido: dict) -> Path:
    """Etiqueta A6 horizontal con remitente (nombre de pila y ciudad), destino, guía y QR."""
    destino = directorio_operacion() / "etiquetas" / f"{rma['rma']}.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)

    ancho, alto = landscape(A6)
    pdf = canvas.Canvas(str(destino), pagesize=(ancho, alto))
    pdf.setTitle(f"Etiqueta de devolución {rma['rma']}")

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(8 * mm, alto - 12 * mm, "EcoMarket · Etiqueta de devolución")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(8 * mm, alto - 17 * mm, f"{rma['carrier']} · Recolección sin costo")

    y = alto - 27 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(8 * mm, y, "REMITENTE")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(8 * mm, y - 5 * mm, f"{rma['customer_first_name']} · {_ciudad(pedido)}")
    pdf.drawString(8 * mm, y - 10 * mm, f"Pedido {rma['tracking_number']}")

    y -= 19 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(8 * mm, y, "DESTINATARIO")
    pdf.setFont("Helvetica", 9)
    for i, linea in enumerate(CENTRO_DEVOLUCIONES):
        pdf.drawString(8 * mm, y - (5 + 5 * i) * mm, linea)

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(8 * mm, 14 * mm, f"RMA: {rma['rma']}")
    pdf.drawString(8 * mm, 8 * mm, f"Guía: {rma['waybill_number']}")

    qr = QrCodeWidget(f"{rma['rma']}|{rma['waybill_number']}|{rma['tracking_number']}")
    x0, y0, x1, y1 = qr.getBounds()
    lado = 38 * mm
    dibujo = Drawing(lado, lado, transform=[lado / (x1 - x0), 0, 0, lado / (y1 - y0), 0, 0])
    dibujo.add(qr)
    renderPDF.draw(dibujo, pdf, ancho - lado - 6 * mm, 10 * mm)

    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(ancho - 6 * mm, 6 * mm, f"Producto: {rma['product'][:45]}")
    pdf.showPage()
    pdf.save()
    return destino.relative_to(RAIZ) if destino.is_relative_to(RAIZ) else destino


# ---------------------------------------------------------------------------
# Mesa de ayuda
# ---------------------------------------------------------------------------


def crear_ticket(motivo: str, resumen: str, tracking_number: str | None, hoy: date) -> dict:
    """Registra un caso para un asesor humano (manual de políticas, §7)."""
    with _candado:
        tickets = _leer("tickets.json")
        ticket = {
            "ticket_id": _siguiente_id("TCK", tickets, hoy, 4),
            "reason": motivo,
            "summary": resumen,
            "tracking_number": tracking_number,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "response_time": "24 horas",
            "business_hours": "Lunes a sábado, 7:00 a. m. a 8:00 p. m.",
        }
        tickets.append(ticket)
        _escribir("tickets.json", tickets)
    return ticket
