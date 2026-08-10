"""PDF compacto del historial de precios de combustible de Distric C."""
from __future__ import annotations

import io
from decimal import Decimal

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .pdf_branding import draw_simple_pdf_branding


DARK = colors.HexColor("#23262b")
RED = colors.HexColor("#d71920")
MUTED = colors.HexColor("#6b7280")
LIGHT = colors.HexColor("#f5f6f8")


def _money(value) -> str:
    if value is None:
        return "-"
    try:
        return f"${Decimal(str(value)):.4f}"
    except Exception:
        return "-"


def construir_pdf_historial_precios(historial) -> bytes:
    """Genera un PDF paginado con todos los ajustes de precio disponibles."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.35 * cm,
        leftMargin=1.35 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.45 * cm,
        title="Historial de precios de combustible - Distric C",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "FuelTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=DARK,
        spaceAfter=3,
    )
    subtitle = ParagraphStyle(
        "FuelSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=MUTED,
        spaceAfter=10,
    )
    empty = ParagraphStyle(
        "FuelEmpty",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        textColor=MUTED,
        fontSize=9,
        leading=13,
    )

    rows = [["Fecha", "Combustible", "Anterior / L", "Nuevo / L", "Valor ingresado", "Administrador"]]
    for ajuste in historial:
        fecha = timezone.localtime(ajuste.fecha_ajuste).strftime("%d/%m/%Y %H:%M") if ajuste.fecha_ajuste else "-"
        unidad = "gal" if ajuste.unidad_ingresada == "GALON" else "L"
        admin = "Sistema"
        if ajuste.administrador:
            admin = f"{ajuste.administrador.nombre_usuario} {ajuste.administrador.apellido_usuario}".strip()
        rows.append([
            fecha,
            ajuste.get_tipo_display(),
            _money(ajuste.precio_anterior_litro),
            _money(ajuste.precio_nuevo_litro),
            f"{_money(ajuste.valor_ingresado)} / {unidad}",
            admin,
        ])

    story = [
        Paragraph("Historial de precios de combustible", title),
        Paragraph(
            "Registro de ajustes realizados por los administradores. Los cálculos internos conservan el precio equivalente por litro, aunque el valor haya sido ingresado por galón.",
            subtitle,
        ),
    ]

    if len(rows) == 1:
        story.append(Spacer(1, 0.7 * cm))
        story.append(Paragraph("Todavía no existen ajustes registrados.", empty))
    else:
        table = Table(
            rows,
            repeatRows=1,
            colWidths=[2.75 * cm, 2.15 * cm, 2.0 * cm, 2.0 * cm, 2.55 * cm, 4.1 * cm],
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7.2),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 7.1),
            ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d8dde3")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ]))
        story.append(table)

    doc.build(
        story,
        onFirstPage=lambda canvas, d: draw_simple_pdf_branding(canvas, d, "DISTRIC C - PRECIOS DE COMBUSTIBLE"),
        onLaterPages=lambda canvas, d: draw_simple_pdf_branding(canvas, d, "DISTRIC C - PRECIOS DE COMBUSTIBLE"),
    )
    return buffer.getvalue()
