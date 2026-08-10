"""Respaldo persistente de informes PDF de viajes en Cloudinary."""
from __future__ import annotations

import io

import cloudinary
import cloudinary.uploader
from django.conf import settings

from .models import ReportePDFViaje


def _configurar_cloudinary() -> None:
    config = getattr(settings, 'CLOUDINARY_STORAGE', {}) or {}
    cloud_name = str(config.get('CLOUD_NAME') or '').strip()
    api_key = str(config.get('API_KEY') or '').strip()
    api_secret = str(config.get('API_SECRET') or '').strip()

    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError('Cloudinary no tiene sus credenciales completas en Render.')

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def respaldar_pdf_viaje(viaje, contenido: bytes, unidad_combustible='LITROS') -> ReportePDFViaje:
    """Sube/actualiza el PDF del viaje y guarda su referencia en PostgreSQL.

    El PDF se conserva como recurso RAW para que Cloudinary lo almacene sin
    transformaciones. El public_id incluye la extensión, como requiere RAW.
    """
    if not contenido:
        raise ValueError('El PDF generado está vacío.')

    unidad = str(unidad_combustible or 'LITROS').strip().upper()
    if unidad not in {'LITROS', 'GALONES'}:
        unidad = 'LITROS'

    _configurar_cloudinary()

    etiqueta = 'prueba' if getattr(viaje, 'es_prueba_administrativa', False) else 'viaje'
    sufijo = 'galones' if unidad == 'GALONES' else 'litros'
    nombre_archivo = f'{etiqueta}_{viaje.id_viaje}_distric_c_{sufijo}.pdf'
    carpeta = f'distric_c/reportes/viajes/{viaje.id_viaje}'

    resultado = cloudinary.uploader.upload(
        io.BytesIO(contenido),
        resource_type='raw',
        folder=carpeta,
        public_id=nombre_archivo,
        overwrite=True,
        invalidate=True,
        use_filename=False,
        unique_filename=False,
    )

    public_id = str(resultado.get('public_id') or '').strip()
    secure_url = str(resultado.get('secure_url') or resultado.get('url') or '').strip()
    if not public_id or not secure_url:
        raise RuntimeError('Cloudinary no devolvió la referencia del PDF.')

    respaldo, _ = ReportePDFViaje.objects.update_or_create(
        viaje=viaje,
        unidad_combustible=unidad,
        defaults={
            'nombre_archivo': nombre_archivo,
            'cloudinary_public_id': public_id,
            'cloudinary_url': secure_url,
            'tamanio_bytes': len(contenido),
        },
    )
    return respaldo
