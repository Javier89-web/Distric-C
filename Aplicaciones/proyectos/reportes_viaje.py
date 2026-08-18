"""Generación del informe PDF consolidado de un viaje.

El informe incluye un mapa general y un mapa independiente por cada tramo. Los
mapas muestran la alternativa planificada y, cuando existen puntos GPS, el
recorrido realmente registrado por el dispositivo.
"""
from __future__ import annotations

import io
import math
from typing import Iterable
from xml.sax.saxutils import escape

import requests
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .pdf_branding import draw_pdf_logos, draw_pdf_watermark, validador_pdf

DARK = colors.HexColor("#23262b")
RED = colors.HexColor("#d71920")
BLUE = colors.HexColor("#2563eb")
GRAY = colors.HexColor("#f4f5f7")
MUTED = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#e5e7eb")
ROUTE_COLORS = [
    "0xd71920ff",
    "0x7c3aedff",
    "0x0f766eff",
    "0xd97706ff",
    "0x2563ebff",
    "0x0891b2ff",
]


def _number(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


LITROS_POR_GALON = 3.785411784


def _combustible_texto(valor_litros, unidad_combustible="LITROS") -> str:
    litros = _number(valor_litros)
    if (unidad_combustible or "").upper() == "GALONES":
        return f"{litros / LITROS_POR_GALON:.3f} gal"
    return f"{litros:.3f} L"


def _evidencia_image(tramo, max_width=9.0 * cm, max_height=5.5 * cm):
    archivo = getattr(tramo, "evidencia_entrega", None)
    if not archivo:
        return None
    try:
        archivo.open("rb")
        contenido = archivo.read()
        archivo.close()
        if not contenido:
            return None
        from PIL import Image as PILImage
        imagen_pil = PILImage.open(io.BytesIO(contenido))
        ancho, alto = imagen_pil.size
        if not ancho or not alto:
            return None
        escala = min(max_width / ancho, max_height / alto)
        return Image(io.BytesIO(contenido), width=ancho * escala, height=alto * escala)
    except Exception:
        return None


def _text(value, default="-") -> str:
    value = str(value or "").strip()
    return value or default


def _paragraph_text(value, default="-") -> str:
    """Texto seguro para los mini-markups que interpreta ReportLab."""
    return escape(_text(value, default))


def _route_letters(total_points: int) -> list[str]:
    return [chr(65 + index) for index in range(min(total_points, 26))]


def _route_labels(total_points: int, numeric: bool = False) -> list[str]:
    if numeric:
        return [str(index) for index in range(total_points)]
    return _route_letters(total_points)


def _route_sequence(tramos, numeric: bool = False) -> tuple[str, list[tuple[str, str]]]:
    tramos = list(tramos or [])
    if not tramos:
        return "", []
    nombres = [_text(tramos[0].origen_nombre)] + [_text(t.destino_nombre) for t in tramos]
    etiquetas = _route_labels(len(nombres), numeric=numeric)
    secuencia = " → ".join(etiquetas)
    leyenda = list(zip(etiquetas, nombres[:len(etiquetas)]))
    return secuencia, leyenda


def _valid_coords(values) -> list[list[float]]:
    result: list[list[float]] = []
    for point in values or []:
        try:
            lat, lon = float(point[0]), float(point[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if not result or result[-1] != [lat, lon]:
            result.append([lat, lon])
    return result


def _planned_coords(tramo) -> list[list[float]]:
    return _valid_coords(tramo.geometria_ruta or [])


def _gps_coords(tramo) -> list[list[float]]:
    try:
        puntos = list(tramo.puntos_gps.all())
    except Exception:
        puntos = []
    return _valid_coords([[p.latitud, p.longitud] for p in puntos])


def _encode_polyline(coords: list[list[float]]) -> str:
    result = []
    previous_lat = previous_lng = 0
    for lat, lng in coords:
        lat_i = int(round(lat * 1e5))
        lng_i = int(round(lng * 1e5))
        for value in (lat_i - previous_lat, lng_i - previous_lng):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                result.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            result.append(chr(value + 63))
        previous_lat, previous_lng = lat_i, lng_i
    return "".join(result)


def _sample(coords: list[list[float]], max_points=150) -> list[list[float]]:
    if len(coords) <= max_points:
        return coords
    step = max(1, math.ceil(len(coords) / max_points))
    sampled = coords[::step]
    if sampled[-1] != coords[-1]:
        sampled.append(coords[-1])
    return sampled


def _static_map(
    planned_paths: list[list[list[float]]],
    gps_paths: list[list[list[float]]] | None = None,
    maptype="roadmap",
    marker_labels: list[str] | None = None,
) -> bytes | None:
    key = (getattr(settings, "GOOGLE_MAPS_SERVER_API_KEY", "") or "").strip()
    planned_paths = [p for p in planned_paths if len(p) >= 2]
    gps_paths = [p for p in (gps_paths or []) if len(p) >= 2]
    if not key or not planned_paths:
        return None

    path_params = []
    for index, coords in enumerate(planned_paths):
        encoded = _encode_polyline(_sample(coords, 125))
        color = ROUTE_COLORS[index % len(ROUTE_COLORS)]
        path_params.append(f"color:{color}|weight:5|enc:{encoded}")
    for coords in gps_paths:
        encoded = _encode_polyline(_sample(coords, 125))
        path_params.append(f"color:0x2563ebff|weight:4|enc:{encoded}")

    route_points = [planned_paths[0][0]] + [path[-1] for path in planned_paths]
    route_letters = marker_labels if marker_labels and len(marker_labels) == len(route_points) else _route_letters(len(route_points))
    params = [
        ("size", "640x360"),
        ("scale", "2"),
        ("maptype", maptype),
        ("language", "es"),
        ("region", "EC"),
    ]
    params.extend(("path", value) for value in path_params)
    for index, (letter, point) in enumerate(zip(route_letters, route_points)):
        marker_color = "0x2563eb" if index == 0 else ("0xd71920" if index == len(route_points) - 1 else "0x23262b")
        params.append(("markers", f"color:{marker_color}|label:{letter}|{point[0]},{point[1]}"))
    params.append(("key", key))
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/staticmap",
            params=params,
            timeout=15,
        )
        if response.status_code == 200 and response.headers.get(
            "content-type", ""
        ).startswith("image/"):
            return response.content
    except requests.RequestException:
        return None
    return None


def _schematic_map(
    planned_paths: list[list[list[float]]],
    gps_paths: list[list[list[float]]] | None = None,
    marker_labels: list[str] | None = None,
) -> bytes:
    from PIL import Image as PILImage, ImageDraw

    planned_paths = [p for p in planned_paths if p]
    gps_paths = [p for p in (gps_paths or []) if p]
    all_points = [p for path in planned_paths + gps_paths for p in path]
    width, height = 1280, 650
    canvas = PILImage.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((1, 1, width - 2, height - 2), outline="#d1d5db", width=2)
    draw.text((28, 22), "Esquema local de las rutas registradas", fill="#23262b")

    if len(all_points) < 2:
        draw.text(
            (28, 70),
            "No existe geometría suficiente para representar la ruta.",
            fill="#6b7280",
        )
    else:
        latitudes = [p[0] for p in all_points]
        longitudes = [p[1] for p in all_points]
        min_lat, max_lat = min(latitudes), max(latitudes)
        min_lon, max_lon = min(longitudes), max(longitudes)
        lat_range = max(max_lat - min_lat, 1e-6)
        lon_range = max(max_lon - min_lon, 1e-6)
        margin = 65

        def project(point):
            lat, lon = point
            x = margin + (lon - min_lon) / lon_range * (width - margin * 2)
            y = height - margin - (lat - min_lat) / lat_range * (height - margin * 2)
            return int(x), int(y)

        colors_plan = ["#d71920", "#7c3aed", "#0f766e", "#d97706", "#0891b2"]
        for index, path in enumerate(planned_paths):
            projected = [project(p) for p in path]
            if len(projected) >= 2:
                draw.line(
                    projected,
                    fill=colors_plan[index % len(colors_plan)],
                    width=6,
                    joint="curve",
                )
        for path in gps_paths:
            projected = [project(p) for p in path]
            if len(projected) >= 2:
                draw.line(projected, fill="#2563eb", width=4, joint="curve")

        route_points = [planned_paths[0][0]] + [path[-1] for path in planned_paths]
        route_letters = marker_labels if marker_labels and len(marker_labels) == len(route_points) else _route_letters(len(route_points))
        for index, (letter, point) in enumerate(zip(route_letters, route_points)):
            projected = project(point)
            fill = "#2563eb" if index == 0 else ("#d71920" if index == len(route_points) - 1 else "#23262b")
            draw.ellipse(
                (projected[0] - 12, projected[1] - 12, projected[0] + 12, projected[1] + 12),
                fill=fill, outline="white", width=3,
            )
            draw.text((projected[0] - 3, projected[1] - 7), letter, fill="white")

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def _map_image(
    planned_paths: list[list[list[float]]],
    gps_paths: list[list[list[float]]] | None = None,
    width=25.4 * cm,
    height=10.7 * cm,
    marker_labels: list[str] | None = None,
) -> Image:
    content = _static_map(planned_paths, gps_paths, marker_labels=marker_labels) or _schematic_map(
        planned_paths, gps_paths, marker_labels=marker_labels
    )
    return Image(io.BytesIO(content), width=width, height=height)


def _header_footer(canvas, doc):
    canvas.saveState()
    page_width, page_height = doc.pagesize
    draw_pdf_watermark(canvas, doc.pagesize)
    canvas.setFillColor(DARK)
    canvas.rect(0, page_height - 1.45 * cm, page_width, 1.45 * cm, fill=1, stroke=0)
    draw_pdf_logos(canvas, doc.pagesize, y_from_top=0.22 * cm)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(page_width / 2, page_height - 0.82 * cm, "DISTRIC C · INFORME DE VIAJE")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(page_width - 1.35 * cm, 0.65 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _summary_table(viaje, tramos, unidad_combustible="LITROS"):
    summary = [
        ["Estado", "Tramos", "Distancia estimada", "Distancia GPS", "Tiempo estimado", "Tiempo real"],
        [
            viaje.get_estado_display(),
            str(viaje.numero_tramos if getattr(viaje, "es_plan_general", False) else viaje.tramos_completados),
            f"{_number(viaje.distancia_estimada_total_km):.2f} km",
            f"{_number(viaje.distancia_real_total_km):.2f} km",
            f"{_number(viaje.tiempo_estimado_total_min):.1f} min",
            f"{_number(viaje.tiempo_real_total_min):.1f} min",
        ],
        ["Combustible IA", "Costo estimado", "Carga inicial", "Carga final", "Peso entregado", "Modelo"],
        [
            _combustible_texto(viaje.consumo_estimado_total_l, unidad_combustible),
            f"${_number(viaje.costo_estimado_total):.2f}",
            f"{_number(viaje.carga_inicial_kg):.2f} kg",
            f"{_number(viaje.carga_final_kg):.2f} kg",
            f"{sum((_number(t.peso_entregado_kg) for t in tramos), 0.0):.2f} kg",
            "Random Forest + Dijkstra",
        ],
    ]
    table = Table(summary, colWidths=[4.25 * cm] * 6)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 2), (-1, 2), DARK),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), GRAY),
        ("BACKGROUND", (0, 3), (-1, 3), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def construir_pdf_viaje(viaje, tramos: Iterable, unidad_combustible="LITROS") -> bytes:
    tramos = list(tramos)
    unidad_combustible = (unidad_combustible or "LITROS").upper()
    if unidad_combustible not in {"LITROS", "GALONES"}:
        unidad_combustible = "LITROS"
    buffer = io.BytesIO()
    pagesize = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.95 * cm,
        bottomMargin=1.25 * cm,
        title=f"Informe de viaje {viaje.id_viaje} - Distric C",
        author="Distric C",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleDC", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=DARK, alignment=TA_LEFT, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="SubDC", parent=styles["BodyText"], fontSize=9.5,
        leading=13, textColor=MUTED, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionDC", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, leading=17, textColor=DARK, spaceBefore=7, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="BodyDC", parent=styles["BodyText"], fontSize=8.4,
        leading=11.5, textColor=DARK,
    ))
    styles.add(ParagraphStyle(
        name="SmallDC", parent=styles["BodyText"], fontSize=7.4,
        leading=9.5, textColor=MUTED,
    ))
    styles.add(ParagraphStyle(
        name="SegmentTitleDC", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=11, textColor=colors.white,
    ))

    planned_paths = [_planned_coords(t) for t in tramos]
    gps_paths = [_gps_coords(t) for t in tramos]
    planned_paths = [p for p in planned_paths if len(p) >= 2]
    gps_paths = [p for p in gps_paths if len(p) >= 2]

    es_plan_general = bool(getattr(viaje, "es_plan_general", False))
    if es_plan_general:
        tipo_registro = "Plan general de tramos"
    else:
        tipo_registro = "Prueba administrativa" if getattr(viaje, "es_prueba_administrativa", False) else "Viaje operativo"
    etiquetas_ruta = _route_labels(len(tramos) + 1, numeric=es_plan_general)
    secuencia_ruta, leyenda_ruta = _route_sequence(tramos, numeric=es_plan_general)
    ejecutor = ""
    if getattr(viaje, "administrador_ejecutor", None):
        ejecutor = (
            f" · Ejecutada por {_paragraph_text(viaje.administrador_ejecutor.nombre_usuario)} "
            f"{_paragraph_text(viaje.administrador_ejecutor.apellido_usuario, '')}"
        )

    story = [
        Paragraph(f"Informe consolidado · {tipo_registro} #{viaje.id_viaje}", styles["TitleDC"]),
        Paragraph(
            f"Vehículo {_paragraph_text(viaje.vehiculo.matricula_vehiculo)} · "
            f"Conductor {_paragraph_text(viaje.usuario.nombre_usuario)} {_paragraph_text(viaje.usuario.apellido_usuario, '')} · "
            f"Inicio {viaje.fecha_creacion.strftime('%d/%m/%Y %H:%M') if viaje.fecha_creacion else '-'}"
            f"{ejecutor}",
            styles["SubDC"],
        ),
        _summary_table(viaje, tramos, unidad_combustible),
        Paragraph(
            f"Unidad de combustible seleccionada para este informe: {'galones (US)' if unidad_combustible == 'GALONES' else 'litros'}.",
            styles["SmallDC"],
        ),
        Spacer(1, 0.20 * cm),
    ]
    if secuencia_ruta:
        leyenda_texto = " · ".join(
            f"<b>{letra}</b>: {_paragraph_text(nombre)}" for letra, nombre in leyenda_ruta
        )
        story.extend([
            Paragraph(f"<b>Secuencia del recorrido:</b> {secuencia_ruta}", styles["BodyDC"]),
            Paragraph(leyenda_texto, styles["SmallDC"]),
            Spacer(1, 0.12 * cm),
        ])
    story.append(Paragraph("Mapa general de la jornada", styles["SectionDC"]))
    if planned_paths:
        story.append(_map_image(planned_paths, gps_paths, height=9.5 * cm, marker_labels=etiquetas_ruta))
        story.append(Paragraph(
            "Líneas de colores: rutas planificadas por tramo. Línea azul: posiciones GPS registradas cuando estuvieron disponibles.",
            styles["SmallDC"],
        ))
    else:
        story.append(Paragraph("No existe geometría suficiente para el mapa general.", styles["BodyDC"]))

    # Tabla consolidada antes de los mapas individuales.
    story.extend([Spacer(1, 0.2 * cm), Paragraph("Resultados por tramo", styles["SectionDC"])])
    data = [[
        "Tramo" if es_plan_general else "Parte", "Origen → destino", "Estado", "Dist. est.", "Dist. GPS",
        "Tiempo est.", "Tiempo real", "Consumo IA", "Carga inicial", "Entregado", "Carga final",
    ]]
    for tramo in tramos:
        numero_tramo = tramo.orden - 1 if es_plan_general else tramo.orden
        data.append([
            str(numero_tramo),
            Paragraph(f"{_paragraph_text(tramo.origen_nombre)} → {_paragraph_text(tramo.destino_nombre)}", styles["SmallDC"]),
            tramo.get_estado_display(),
            f"{_number(tramo.distancia_estimada_km):.2f} km",
            f"{_number(tramo.distancia_real_km):.2f} km",
            f"{_number(tramo.tiempo_estimado_min):.1f} min",
            f"{_number(tramo.tiempo_real_min):.1f} min",
            _combustible_texto(tramo.consumo_estimado_l, unidad_combustible),
            f"{_number(tramo.carga_inicio_kg):.2f} kg",
            f"{_number(tramo.peso_entregado_kg):.2f} kg",
            f"{_number(tramo.carga_restante_kg):.2f} kg",
        ])
    table = Table(
        data,
        colWidths=[1.0 * cm, 6.2 * cm, 2.15 * cm, 1.75 * cm, 1.75 * cm,
                   1.8 * cm, 1.8 * cm, 1.85 * cm, 2.0 * cm, 1.9 * cm, 2.0 * cm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.1),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    # Una página (o más, si la entrega es extensa) para cada parte del viaje.
    for index, tramo in enumerate(tramos):
        planned = _planned_coords(tramo)
        gps = _gps_coords(tramo)
        etiquetas = etiquetas_ruta
        etiqueta_tramo = (
            f"{etiquetas[index]} → {etiquetas[index + 1]}"
            if index + 1 < len(etiquetas) else f"Tramo {tramo.orden}"
        )
        story.append(PageBreak())
        numero_tramo = tramo.orden - 1 if es_plan_general else tramo.orden
        story.append(Paragraph(
            f"{'Tramo' if es_plan_general else 'Parte'} {numero_tramo} · {etiqueta_tramo}: {_paragraph_text(tramo.origen_nombre)} → {_paragraph_text(tramo.destino_nombre)}",
            styles["TitleDC"],
        ))
        story.append(Paragraph(
            f"Estado: {tramo.get_estado_display()} · "
            f"Ruta seleccionada: {_paragraph_text(getattr(tramo.ruta_seleccionada, 'tipo', ''), 'No registrada')} · "
            f"Modelo: {_paragraph_text(tramo.modelo_ia, 'Fórmula de respaldo')}",
            styles["SubDC"],
        ))

        if len(planned) >= 2:
            story.append(_map_image(
                [planned],
                [gps] if len(gps) >= 2 else [],
                height=10.7 * cm,
                marker_labels=[etiquetas[index], etiquetas[index + 1]],
            ))
            story.append(Paragraph(
                "Rojo: alternativa planificada. Azul: recorrido GPS real del vehículo.",
                styles["SmallDC"],
            ))
        else:
            story.append(Paragraph("No existe geometría suficiente para este tramo.", styles["BodyDC"]))

        metrics = [
            ["Distancia estimada", "Distancia GPS", "Tiempo estimado", "Tiempo real", "Consumo IA", "Costo estimado"],
            [
                f"{_number(tramo.distancia_estimada_km):.2f} km",
                f"{_number(tramo.distancia_real_km):.2f} km",
                f"{_number(tramo.tiempo_estimado_min):.1f} min",
                f"{_number(tramo.tiempo_real_min):.1f} min",
                _combustible_texto(tramo.consumo_estimado_l, unidad_combustible),
                f"${_number(tramo.costo_estimado):.2f}",
            ],
            ["Carga inicial", "Peso entregado", "Carga restante", "Tráfico", "Clima", "Temperatura"],
            [
                f"{_number(tramo.carga_inicio_kg):.2f} kg",
                f"{_number(tramo.peso_entregado_kg):.2f} kg",
                f"{_number(tramo.carga_restante_kg):.2f} kg",
                _text(tramo.trafico_descripcion),
                _text(tramo.clima_descripcion),
                f"{_number(tramo.temperatura_c):.1f} °C" if tramo.temperatura_c is not None else "No reportada",
            ],
        ]
        metrics_table = Table(metrics, colWidths=[4.25 * cm] * 6)
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 2), (-1, 2), DARK),
            ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
            ("BACKGROUND", (0, 1), (-1, 1), GRAY),
            ("BACKGROUND", (0, 3), (-1, 3), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([Spacer(1, 0.18 * cm), metrics_table])

        detail = tramo.detalle_prediccion or {}
        traffic = detail.get("trafico") or {}
        weather = detail.get("clima") or {}
        deliveries = list(tramo.entregas_realizadas.all())
        if deliveries:
            delivery_lines = []
            for entrega in deliveries:
                unidad = entrega.unidad_carga if entrega.cantidad_entregada == 1 else entrega.unidad_carga_plural
                marca = (
                    f"{_paragraph_text(entrega.marca_producto)} · "
                    if entrega.marca_producto
                    else ""
                )
                delivery_lines.append(
                    f"{_paragraph_text(entrega.producto_nombre)}: "
                    f"{marca}{_paragraph_text(entrega.presentacion_descriptiva)}; "
                    f"{entrega.cantidad_entregada} {_paragraph_text(unidad)}; "
                    f"{_number(entrega.peso_entregado_kg):.2f} kg"
                )
            delivery_text = "<br/>".join(delivery_lines)
        else:
            delivery_text = "No se registraron productos entregados."

        rows = [
            ["Fuente de tráfico", _text(traffic.get("fuente"), "Registro del tramo")],
            ["Fuente del clima", _text(weather.get("fuente"), "Registro del tramo")],
            ["Productos entregados", Paragraph(delivery_text, styles["BodyDC"])],
            ["Nota de cierre", Paragraph(_paragraph_text(tramo.nota_finalizacion, "Sin nota"), styles["BodyDC"])],
        ]
        detail_table = Table(rows, colWidths=[4.2 * cm, 21.3 * cm])
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), GRAY),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([Spacer(1, 0.2 * cm), detail_table])

        if not es_plan_general:
            evidencia = _evidencia_image(tramo)
            if evidencia:
                story.extend([
                    Spacer(1, 0.18 * cm),
                    Paragraph("Evidencia fotográfica de la entrega", styles["SectionDC"]),
                    evidencia,
                    Paragraph(
                        "Imagen registrada al finalizar el tramo y almacenada como evidencia de la entrega.",
                        styles["SmallDC"],
                    ),
                ])
            else:
                story.extend([
                    Spacer(1, 0.15 * cm),
                    Paragraph("Evidencia fotográfica: no disponible en este registro.", styles["SmallDC"]),
                ])

    # Página final preparada para la validación manuscrita del informe.
    validador = validador_pdf()
    story.extend([
        PageBreak(),
        Paragraph("Solicitud de validación del informe", styles["TitleDC"]),
        Paragraph(
            "Este apartado deja constancia de la persona designada para revisar y validar el informe. "
            "La validez se completa con la firma manuscrita y la fecha de revisión.",
            styles["SubDC"],
        ),
        Spacer(1, 0.4 * cm),
    ])
    firma_data = [
        ["Nombres", _paragraph_text(validador.get("nombres"))],
        ["Apellidos", _paragraph_text(validador.get("apellidos"))],
        ["Documento / NUI", _paragraph_text(validador.get("documento"))],
        ["Calidad", _paragraph_text(validador.get("cargo"))],
        ["Informe", f"{tipo_registro} #{viaje.id_viaje}"],
        ["Unidad de combustible", "Galones (US)" if unidad_combustible == "GALONES" else "Litros"],
    ]
    firma_table = Table(firma_data, colWidths=[5.0 * cm, 14.0 * cm], hAlign="LEFT")
    firma_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), GRAY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([
        firma_table,
        Spacer(1, 1.2 * cm),
        Paragraph("Firma de validación", styles["SectionDC"]),
        Spacer(1, 1.3 * cm),
        Table(
            [["________________________________________", "________________________________________"],
             ["Firma", "Fecha de validación"]],
            colWidths=[9.5 * cm, 9.5 * cm],
            hAlign="LEFT",
            style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (-1, 1), MUTED),
            ]),
        ),
        Spacer(1, 0.5 * cm),
        Paragraph(
            "La presencia de esta sección no implica que el documento haya sido firmado; funciona como solicitud y espacio de validación.",
            styles["SmallDC"],
        ),
    ])

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()
