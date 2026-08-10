"""Identidad visual común para los PDF del proyecto Distric C."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader


def _static_path(relative_path: str) -> str | None:
    encontrado = finders.find(relative_path)
    if isinstance(encontrado, (list, tuple)):
        encontrado = encontrado[0] if encontrado else None
    if encontrado:
        return str(encontrado)

    candidato = Path(settings.BASE_DIR) / "proyectos" / "static" / relative_path
    return str(candidato) if candidato.exists() else None


def utc_logo_path() -> str | None:
    return _static_path("img/branding/utc-logo.png")


def utc_watermark_path() -> str | None:
    return _static_path("img/branding/utc-watermark.png")


def distric_logo_path() -> str | None:
    return _static_path("img/branding/distric-c-logo.png")


def draw_pdf_watermark(canvas, pagesize) -> None:
    """Dibuja la firma UTC pequeña en una esquina inferior del PDF."""
    path = utc_watermark_path()
    if not path:
        return

    width, _height = pagesize
    # La imagen ya contiene transparencia; el tamaño pequeño evita tapar tablas,
    # mapas o firmas. Se ubica abajo a la izquierda para no competir con la
    # numeración de página que normalmente va a la derecha.
    target_width = min(width * 0.19, 4.2 * cm)
    target_height = target_width * (224 / 497)
    x = 1.05 * cm
    y = 0.42 * cm

    try:
        canvas.drawImage(
            ImageReader(path),
            x,
            y,
            width=target_width,
            height=target_height,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception:
        # El PDF no debe fallar solo porque un recurso visual no esté disponible.
        pass


def draw_pdf_logos(canvas, pagesize, y_from_top=0.25 * cm) -> None:
    """Agrega ambos logos en tamaño pequeño sin salir del margen superior."""
    width, height = pagesize
    distric = distric_logo_path()
    utc = utc_logo_path()

    distric_w = 1.80 * cm
    distric_h = 0.98 * cm
    utc_w = 1.82 * cm
    utc_h = 0.82 * cm
    top_y = height - y_from_top

    try:
        if distric:
            canvas.drawImage(
                ImageReader(distric),
                1.20 * cm,
                top_y - distric_h,
                width=distric_w,
                height=distric_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        if utc:
            canvas.drawImage(
                ImageReader(utc),
                width - 1.20 * cm - utc_w,
                top_y - utc_h,
                width=utc_w,
                height=utc_h,
                preserveAspectRatio=True,
                mask="auto",
            )
    except Exception:
        pass


def draw_simple_pdf_branding(canvas, doc=None, title="DISTRIC C") -> None:
    """Callback para SimpleDocTemplate: watermark, logos, título y paginación."""
    pagesize = doc.pagesize if doc is not None else canvas._pagesize
    width, height = pagesize
    canvas.saveState()
    draw_pdf_watermark(canvas, pagesize)
    draw_pdf_logos(canvas, pagesize, y_from_top=0.55 * cm)

    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColorRGB(0.20, 0.20, 0.22)
    canvas.drawCentredString(width / 2, height - 0.72 * cm, title)

    if doc is not None:
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColorRGB(0.42, 0.45, 0.49)
        canvas.drawRightString(width - 1.2 * cm, 0.55 * cm, f"Página {doc.page}")
    canvas.restoreState()


def validador_pdf() -> dict[str, str]:
    """Datos de la persona indicada en la documentación para la validación final."""
    return {
        "nombres": str(getattr(settings, "PDF_VALIDADOR_NOMBRES", "")).strip(),
        "apellidos": str(getattr(settings, "PDF_VALIDADOR_APELLIDOS", "")).strip(),
        "documento": str(getattr(settings, "PDF_VALIDADOR_DOCUMENTO", "")).strip(),
        "cargo": str(getattr(settings, "PDF_VALIDADOR_CARGO", "Responsable de validación")).strip(),
    }
