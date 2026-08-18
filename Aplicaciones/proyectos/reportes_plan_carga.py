"""PDF formal para los planes de carga de Distric C."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .pdf_branding import draw_simple_pdf_branding


DARK = colors.HexColor("#23262B")
RED = colors.HexColor("#D71920")
MUTED = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F5F6F8")
BORDER = colors.HexColor("#D9DEE5")
SOFT_RED = colors.HexColor("#FFF1F2")


def _texto(valor, defecto="—"):
    texto = str(valor or "").strip()
    return escape(texto) if texto else defecto


def _fecha(valor, incluir_hora=False):
    if not valor:
        return "—"
    try:
        return valor.strftime("%d/%m/%Y %H:%M" if incluir_hora else "%d/%m/%Y")
    except Exception:
        return _texto(valor)


def _numero(valor):
    try:
        return f"{float(valor or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _nombre_usuario(usuario):
    if not usuario:
        return "—"
    nombre = f"{getattr(usuario, 'nombre_usuario', '')} {getattr(usuario, 'apellido_usuario', '')}".strip()
    return nombre or "—"


def _cargo_administrativo(usuario):
    if not usuario:
        return "Administradora"
    try:
        registro = usuario.administrador
    except Exception:
        registro = None
    cargo = str(getattr(registro, "cargo", "") or "").strip()
    return cargo or "Administradora"


def _presentacion_producto(producto):
    if not producto:
        return "—"
    try:
        presentacion = producto.get_presentacion_producto_display()
    except Exception:
        presentacion = getattr(producto, "presentacion_producto", "")
    unidades = getattr(producto, "unidades_por_presentacion", None)
    if presentacion and unidades:
        return f"{presentacion} × {unidades}"
    return str(presentacion or "—")


def _header_footer(canvas, doc):
    draw_simple_pdf_branding(canvas, doc, title="DISTRIC C · PLAN DE CARGA")


def construir_pdf_plan_carga(plan) -> bytes:
    """Genera un informe de salida del plan de carga con detalle y firma."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.35 * cm,
        leftMargin=1.35 * cm,
        topMargin=1.9 * cm,
        bottomMargin=1.35 * cm,
        title=f"Plan de carga {plan.id_plan_carga} - Distric C",
        author="Distric C",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CargaTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=23,
        textColor=DARK,
        alignment=TA_LEFT,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="CargaSub",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=MUTED,
        spaceAfter=9,
    ))
    styles.add(ParagraphStyle(
        name="CargaSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=15,
        textColor=DARK,
        spaceBefore=6,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="CargaBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=DARK,
    ))
    styles.add(ParagraphStyle(
        name="CargaSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.2,
        textColor=MUTED,
    ))

    vehiculo = plan.vehiculo
    conductor = getattr(vehiculo, "usuario", None)
    responsable = plan.confirmado_por or plan.creado_por

    story = [
        Paragraph(f"Plan de carga #{plan.id_plan_carga}", styles["CargaTitle"]),
        Paragraph(
            "Resumen de productos y condiciones previstas para la salida del vehículo.",
            styles["CargaSub"],
        ),
    ]

    # Datos principales de salida.
    story.append(Paragraph("Datos de salida programada", styles["CargaSection"]))
    datos = [
        ["Fecha de salida programada", _fecha(plan.fecha_planificada), "Estado", _texto(plan.get_estado_display())],
        ["Conductor a cargo", _texto(_nombre_usuario(conductor)), "Teléfono", _texto(getattr(conductor, "telefono_usuario", ""))],
        ["Vehículo", _texto(getattr(vehiculo, "matricula_vehiculo", "")), "Modelo", _texto(getattr(vehiculo, "modelo_vehiculo", ""))],
        ["Tipo de vehículo", _texto(vehiculo.get_tipovehiculo_vehiculo_display()), "Combustible", _texto(vehiculo.get_tipocombustible_vehiculo_display())],
        ["Capacidad máxima", f"{_numero(plan.capacidad_kg)} kg", "Peso efectivo", f"{_numero(plan.peso_total_kg)} kg"],
        ["Capacidad disponible", f"{_numero(plan.disponible_kg)} kg", "Revisión del conductor", "REALIZADA" if plan.revisado_por_usuario else "PENDIENTE"],
    ]
    tabla_datos = Table(datos, colWidths=[4.0 * cm, 5.0 * cm, 3.35 * cm, 5.0 * cm])
    tabla_datos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("BACKGROUND", (2, 0), (2, -1), LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([tabla_datos, Spacer(1, 0.22 * cm)])

    # Resumen de peso.
    resumen = [
        ["Peso programado", "Peso efectivo", "Peso descartado", "Disponible"],
        [
            f"{_numero(plan.peso_programado_kg)} kg",
            f"{_numero(plan.peso_total_kg)} kg",
            f"{_numero(plan.peso_descartado_kg)} kg",
            f"{_numero(plan.disponible_kg)} kg",
        ],
    ]
    tabla_resumen = Table(resumen, colWidths=[4.35 * cm] * 4)
    tabla_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(tabla_resumen)

    # Productos.
    story.extend([Spacer(1, 0.22 * cm), Paragraph("Productos asignados", styles["CargaSection"])])
    productos = [[
        "Producto", "Marca", "Presentación", "Asignado", "Actual", "Peso unit.", "Peso efectivo", "Estado"
    ]]
    detalles = list(plan.detalles.all())
    for detalle in detalles:
        producto = detalle.producto
        productos.append([
            Paragraph(_texto(getattr(producto, "nombre_producto", "")), styles["CargaBody"]),
            Paragraph(_texto(getattr(producto, "marca_producto", "")), styles["CargaSmall"]),
            Paragraph(_texto(_presentacion_producto(producto)), styles["CargaSmall"]),
            str(detalle.cantidad),
            str(detalle.cantidad_actual),
            f"{_numero(detalle.peso_unitario_kg)} kg",
            f"{_numero(detalle.peso_actual_kg)} kg",
            _texto(detalle.estado_ajuste),
        ])

    if len(productos) == 1:
        productos.append(["Sin productos", "—", "—", "0", "0", "0.00 kg", "0.00 kg", "—"])

    tabla_productos = Table(
        productos,
        colWidths=[4.1 * cm, 2.25 * cm, 2.55 * cm, 1.25 * cm, 1.15 * cm, 1.65 * cm, 1.85 * cm, 2.0 * cm],
        repeatRows=1,
    )
    tabla_productos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.1),
        ("ALIGN", (3, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_productos)

    # Notas y control administrativo.
    story.extend([Spacer(1, 0.25 * cm), Paragraph("Detalles administrativos", styles["CargaSection"])])
    control = [
        ["Fecha de creación", _fecha(plan.fecha_creacion, True)],
        ["Fecha de revisión del conductor", _fecha(plan.fecha_revision_usuario, True)],
        ["Fecha de confirmación", _fecha(plan.fecha_confirmacion, True)],
        ["Plan preparado por", _texto(_nombre_usuario(plan.creado_por))],
        ["Plan confirmado por", _texto(_nombre_usuario(plan.confirmado_por))],
        ["Observación", Paragraph(_texto(plan.notas, "Sin observaciones registradas."), styles["CargaBody"])],
    ]
    tabla_control = Table(control, colWidths=[5.1 * cm, 12.25 * cm])
    tabla_control.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla_control)

    # Firma de la administradora/responsable del plan.
    story.extend([
        Spacer(1, 0.35 * cm),
        Paragraph("Autorización administrativa", styles["CargaSection"]),
        Paragraph(
            "Espacio destinado a la firma de la responsable administrativa que valida la información del plan antes de la salida.",
            styles["CargaSmall"],
        ),
        Spacer(1, 0.55 * cm),
    ])

    firma_info = Table([
        ["Responsable", _texto(_nombre_usuario(responsable)), "Cargo", _texto(_cargo_administrativo(responsable))],
    ], colWidths=[2.8 * cm, 6.2 * cm, 2.0 * cm, 6.35 * cm])
    firma_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), LIGHT),
        ("BACKGROUND", (2, 0), (2, 0), LIGHT),
        ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.2),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(firma_info)
    story.extend([
        Spacer(1, 1.25 * cm),
        Table(
            [["____________________________________", "____________________________________"],
             ["Firma de la administradora", "Fecha de validación"]],
            colWidths=[8.65 * cm, 8.65 * cm],
            style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 1), (-1, 1), MUTED),
            ]),
        ),
        Spacer(1, 0.25 * cm),
        Paragraph(
            "La firma valida la información registrada en este documento para la salida programada del vehículo.",
            styles["CargaSmall"],
        ),
    ])

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()
