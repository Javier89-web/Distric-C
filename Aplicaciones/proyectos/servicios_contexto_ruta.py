"""Servicios externos y respaldos controlados para el módulo de rutas.

El módulo centraliza:
- búsqueda de destinos mediante Places API (New),
- tráfico mediante Routes API,
- clima mediante Weather API,
- respaldos locales claros cuando una API no está configurada o responde con error.

Los respaldos nunca se presentan como datos en tiempo real: incluyen la fuente y
una descripción explícita para mantener trazabilidad en la tesis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .servicios_google import obtener_clima_google, obtener_trafico_google

CACHE_CONTEXT_SEGUNDOS = 600
CACHE_BUSQUEDA_SEGUNDOS = 900
LATACUNGA = (-0.9336, -78.6142)


def _server_key() -> str:
    return (getattr(settings, "GOOGLE_MAPS_SERVER_API_KEY", "") or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_coord(value: Any, digits: int = 4) -> float:
    return round(_float(value), digits)


def _traffic_description(factor: float) -> str:
    if factor >= 1.45:
        return "tráfico muy alto"
    if factor >= 1.25:
        return "tráfico alto"
    if factor >= 1.08:
        return "tráfico moderado"
    return "tráfico fluido"


def _traffic_local_estimate(at: datetime | None = None) -> dict[str, Any]:
    """Estimación de respaldo por horario local, no dato en tiempo real."""
    current = timezone.localtime(at or timezone.now())
    hour = current.hour + current.minute / 60.0
    weekday = current.weekday()  # 0=lunes

    factor = 1.02
    reason = "circulación normalmente estable para este horario"

    if weekday <= 4 and (6.5 <= hour <= 9.0 or 16.5 <= hour <= 19.5):
        factor = 1.28
        reason = "hora pico laboral estimada"
    elif weekday <= 4 and (11.5 <= hour <= 14.0):
        factor = 1.14
        reason = "movilidad moderada estimada al mediodía"
    elif weekday >= 5 and 10.0 <= hour <= 17.0:
        factor = 1.10
        reason = "movilidad comercial estimada de fin de semana"

    return {
        "disponible": True,
        "api_disponible": False,
        "fuente": "Estimación local por horario",
        "desde_cache": False,
        "factor_trafico": round(factor, 2),
        "descripcion_trafico": _traffic_description(factor),
        "duracion_trafico_min": None,
        "duracion_sin_trafico_min": None,
        "consultado_en": current.strftime("%Y-%m-%d %H:%M"),
        "mensaje": f"Respaldo local utilizado: {reason}. No representa tráfico en tiempo real.",
    }


def _weather_code_description(code: int | None) -> tuple[str, float]:
    descriptions = {
        0: ("cielo despejado", 1.00),
        1: ("principalmente despejado", 1.00),
        2: ("parcialmente nublado", 1.01),
        3: ("nublado", 1.02),
        45: ("niebla", 1.07),
        48: ("niebla con escarcha", 1.08),
        51: ("llovizna ligera", 1.04),
        53: ("llovizna moderada", 1.06),
        55: ("llovizna intensa", 1.08),
        61: ("lluvia ligera", 1.06),
        63: ("lluvia moderada", 1.09),
        65: ("lluvia intensa", 1.13),
        80: ("chubascos ligeros", 1.07),
        81: ("chubascos moderados", 1.10),
        82: ("chubascos intensos", 1.15),
        95: ("tormenta", 1.16),
        96: ("tormenta con granizo", 1.18),
        99: ("tormenta fuerte con granizo", 1.18),
    }
    return descriptions.get(code, ("condición climática estable estimada", 1.00))


def _weather_open_meteo(lat: float, lon: float) -> dict[str, Any] | None:
    """Respaldo gratuito para clima actual. No requiere clave."""
    cache_key = f"open_meteo_current:{_round_coord(lat, 3)}:{_round_coord(lon, 3)}"
    cached = cache.get(cache_key)
    if cached:
        result = dict(cached)
        result["desde_cache"] = True
        return result

    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                "timezone": "America/Guayaquil",
            },
            timeout=8,
        )
        if response.status_code != 200:
            return None
        current = response.json().get("current") or {}
        code = current.get("weather_code")
        description, factor = _weather_code_description(int(code) if code is not None else None)
        precipitation = _float(current.get("precipitation"), 0.0)
        wind = _float(current.get("wind_speed_10m"), 0.0)
        if precipitation > 0:
            factor = min(factor + 0.02, 1.18)
        if wind >= 30:
            factor = min(factor + 0.03, 1.18)

        result = {
            "disponible": True,
            "api_disponible": True,
            "fuente": "Open-Meteo (respaldo)",
            "desde_cache": False,
            "factor_clima": round(factor, 2),
            "descripcion_clima": description,
            "motivo_clima": "Condición actual obtenida mediante servicio climático de respaldo.",
            "temperatura": current.get("temperature_2m"),
            "humedad": current.get("relative_humidity_2m"),
            "nubosidad": None,
            "viento_kmh": wind,
            "precipitacion_mm": precipitation,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "Dato actual de respaldo; Google Weather API no estuvo disponible.",
        }
        cache.set(cache_key, result, CACHE_CONTEXT_SEGUNDOS)
        return result
    except requests.RequestException:
        return None


def _weather_neutral_estimate() -> dict[str, Any]:
    current = timezone.localtime()
    return {
        "disponible": True,
        "api_disponible": False,
        "fuente": "Estimación climática neutral",
        "desde_cache": False,
        "factor_clima": 1.0,
        "descripcion_clima": "condición neutral de respaldo",
        "motivo_clima": "No se recibió información de las APIs; se aplicó un factor neutral para no detener el cálculo.",
        "temperatura": None,
        "humedad": None,
        "nubosidad": None,
        "consultado_en": current.strftime("%Y-%m-%d %H:%M"),
        "mensaje": "Respaldo matemático, no observación meteorológica.",
    }


def obtener_trafico_contexto(lat_origen: float, lon_origen: float, lat_destino: float, lon_destino: float) -> dict[str, Any]:
    result = obtener_trafico_google(lat_origen, lon_origen, lat_destino, lon_destino)
    if result.get("disponible"):
        result = dict(result)
        result["api_disponible"] = True
        result["descripcion_trafico"] = result.get("descripcion_trafico") or _traffic_description(_float(result.get("factor_trafico"), 1.0))
        return result
    fallback = _traffic_local_estimate()
    original_message = result.get("mensaje")
    if original_message:
        fallback["detalle_api"] = original_message
    return fallback


def obtener_clima_contexto(lat: float, lon: float) -> dict[str, Any]:
    result = obtener_clima_google(lat, lon)
    if result.get("disponible"):
        result = dict(result)
        result["api_disponible"] = True
        return result
    fallback = _weather_open_meteo(lat, lon)
    if fallback:
        fallback["detalle_api_google"] = result.get("mensaje", "")
        return fallback
    neutral = _weather_neutral_estimate()
    neutral["detalle_api_google"] = result.get("mensaje", "")
    return neutral


def obtener_factores_ruta(lat_origen: float, lon_origen: float, lat_destino: float, lon_destino: float) -> dict[str, Any]:
    """Obtiene tráfico y clima con trazabilidad de la fuente utilizada."""
    traffic = obtener_trafico_contexto(lat_origen, lon_origen, lat_destino, lon_destino)
    middle_lat = (float(lat_origen) + float(lat_destino)) / 2.0
    middle_lon = (float(lon_origen) + float(lon_destino)) / 2.0
    weather = obtener_clima_contexto(middle_lat, middle_lon)
    return {"trafico": traffic, "clima": weather}


def buscar_lugares_google(query: str, *, lat: float | None = None, lon: float | None = None, max_results: int = 8) -> dict[str, Any]:
    """Busca destinos con Places API (New) desde el servidor.

    Devuelve una estructura estable para el JavaScript y no expone la clave de
    servidor en el navegador.
    """
    text = (query or "").strip()
    if len(text) < 2:
        return {"ok": False, "resultados": [], "mensaje": "Escribe al menos dos caracteres."}

    api_key = _server_key()
    if not api_key:
        return {
            "ok": False,
            "resultados": [],
            "mensaje": "La búsqueda avanzada requiere GOOGLE_MAPS_SERVER_API_KEY con Places API (New).",
        }

    bias_lat = _float(lat, LATACUNGA[0]) if lat is not None else LATACUNGA[0]
    bias_lon = _float(lon, LATACUNGA[1]) if lon is not None else LATACUNGA[1]
    cache_key = f"places_text:{text.lower()}:{_round_coord(bias_lat, 3)}:{_round_coord(bias_lon, 3)}"
    cached = cache.get(cache_key)
    if cached:
        return dict(cached, desde_cache=True)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.primaryTypeDisplayName"
        ),
    }
    payload = {
        "textQuery": text,
        "languageCode": "es-419",
        "regionCode": "EC",
        "pageSize": max(1, min(int(max_results), 10)),
        "locationBias": {
            "circle": {
                "center": {"latitude": bias_lat, "longitude": bias_lon},
                "radius": 40000.0,
            }
        },
    }

    try:
        response = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            detail = ""
            try:
                detail = (response.json().get("error") or {}).get("message", "")
            except ValueError:
                pass
            return {
                "ok": False,
                "resultados": [],
                "mensaje": f"Places API respondió {response.status_code}. {detail}".strip(),
            }

        results = []
        for place in response.json().get("places", []):
            location = place.get("location") or {}
            latitude = location.get("latitude")
            longitude = location.get("longitude")
            if latitude is None or longitude is None:
                continue
            display_name = (place.get("displayName") or {}).get("text") or "Destino"
            type_name = (place.get("primaryTypeDisplayName") or {}).get("text") or "Lugar"
            results.append({
                "id": place.get("id", ""),
                "nombre": display_name,
                "direccion": place.get("formattedAddress") or display_name,
                "tipo": type_name,
                "latitud": float(latitude),
                "longitud": float(longitude),
            })

        result = {
            "ok": True,
            "resultados": results,
            "mensaje": "Resultados obtenidos con Places API (New)." if results else "No se encontraron coincidencias.",
            "fuente": "Google Places API (New)",
            "desde_cache": False,
        }
        cache.set(cache_key, result, CACHE_BUSQUEDA_SEGUNDOS)
        return result
    except requests.RequestException as exc:
        return {"ok": False, "resultados": [], "mensaje": f"No se pudo consultar Places API: {exc}"}
