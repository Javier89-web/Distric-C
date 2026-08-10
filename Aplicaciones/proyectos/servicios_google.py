import re
import requests

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


CACHE_GOOGLE_SEGUNDOS = 600  # 10 minutos


def _api_key_servidor():
    return getattr(settings, "GOOGLE_MAPS_SERVER_API_KEY", "") or ""


def _duracion_google_a_segundos(valor):
    """
    Convierte valores tipo '123.456s' a segundos.
    """
    if not valor:
        return None

    try:
        return float(str(valor).replace("s", "").strip())
    except (TypeError, ValueError):
        return None


def _redondear_coord(valor, decimales=4):
    try:
        return round(float(valor), decimales)
    except (TypeError, ValueError):
        return 0


def _descripcion_trafico(factor):
    if factor >= 1.46:
        return "muy alto"

    if factor >= 1.21:
        return "alto"

    if factor >= 1.06:
        return "moderado"

    return "normal"


def _extraer_numero(obj):
    """
    Intenta sacar un valor numérico de respuestas distintas.
    Sirve para temperature, wind, precipitation, etc.
    """
    if obj is None:
        return None

    if isinstance(obj, (int, float)):
        return float(obj)

    if isinstance(obj, dict):
        for key in ["value", "degrees", "amount", "percent", "kilometersPerHour"]:
            if key in obj:
                try:
                    return float(obj[key])
                except (TypeError, ValueError):
                    pass

        for value in obj.values():
            resultado = _extraer_numero(value)
            if resultado is not None:
                return resultado

    return None


def obtener_trafico_google(lat_origen, lon_origen, lat_destino, lon_destino):
    """
    Consulta Google Routes API para obtener duración con tráfico y sin tráfico.
    Usa cache de 10 minutos.
    """

    api_key = _api_key_servidor()

    if not api_key:
        return {
            "disponible": False,
            "fuente": "Google Routes API",
            "desde_cache": False,
            "factor_trafico": 1.0,
            "descripcion_trafico": "no disponible",
            "duracion_trafico_min": None,
            "duracion_sin_trafico_min": None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "No se configuró GOOGLE_MAPS_SERVER_API_KEY.",
        }

    cache_key = (
        "google_routes_trafico:"
        f"{_redondear_coord(lat_origen)}:"
        f"{_redondear_coord(lon_origen)}:"
        f"{_redondear_coord(lat_destino)}:"
        f"{_redondear_coord(lon_destino)}"
    )

    cached = cache.get(cache_key)
    if cached:
        cached["desde_cache"] = True
        return cached

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters",
    }

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(lat_origen),
                    "longitude": float(lon_origen),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(lat_destino),
                    "longitude": float(lon_destino),
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "es-419",
        "units": "METRIC",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=8
        )

        if response.status_code != 200:
            return {
                "disponible": False,
                "fuente": "Google Routes API",
                "desde_cache": False,
                "factor_trafico": 1.0,
                "descripcion_trafico": "no disponible",
                "duracion_trafico_min": None,
                "duracion_sin_trafico_min": None,
                "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
                "mensaje": f"Google Routes API respondió {response.status_code}.",
            }

        data = response.json()
        rutas = data.get("routes", [])

        if not rutas:
            return {
                "disponible": False,
                "fuente": "Google Routes API",
                "desde_cache": False,
                "factor_trafico": 1.0,
                "descripcion_trafico": "no disponible",
                "duracion_trafico_min": None,
                "duracion_sin_trafico_min": None,
                "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
                "mensaje": "Google no devolvió rutas.",
            }

        ruta = rutas[0]

        duracion_trafico_seg = _duracion_google_a_segundos(ruta.get("duration"))
        duracion_base_seg = _duracion_google_a_segundos(ruta.get("staticDuration"))

        factor_trafico = 1.0

        if duracion_trafico_seg and duracion_base_seg and duracion_base_seg > 0:
            factor_trafico = duracion_trafico_seg / duracion_base_seg

            if factor_trafico < 1.0:
                factor_trafico = 1.0

            if factor_trafico > 1.80:
                factor_trafico = 1.80

        resultado = {
            "disponible": True,
            "fuente": "Google Routes API",
            "desde_cache": False,
            "factor_trafico": round(factor_trafico, 2),
            "descripcion_trafico": _descripcion_trafico(factor_trafico),
            "duracion_trafico_min": round(duracion_trafico_seg / 60, 1) if duracion_trafico_seg else None,
            "duracion_sin_trafico_min": round(duracion_base_seg / 60, 1) if duracion_base_seg else None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "Dato estimado por API al momento de la consulta.",
        }

        cache.set(cache_key, resultado, CACHE_GOOGLE_SEGUNDOS)
        return resultado

    except Exception as e:
        return {
            "disponible": False,
            "fuente": "Google Routes API",
            "desde_cache": False,
            "factor_trafico": 1.0,
            "descripcion_trafico": "no disponible",
            "duracion_trafico_min": None,
            "duracion_sin_trafico_min": None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": f"No se pudo consultar tráfico: {str(e)}",
        }


def _factor_clima_desde_respuesta(data):
    """
    Calcula factor climático de forma conservadora.
    Si el dato no es claro, no exagera.
    """

    weather_condition = data.get("weatherCondition", {}) or {}
    descripcion = ""

    if isinstance(weather_condition, dict):
        descripcion = (
            weather_condition.get("description", {}).get("text")
            or weather_condition.get("displayName", {}).get("text")
            or weather_condition.get("type")
            or ""
        )

    texto = str(descripcion).lower()

    precipitation = data.get("precipitation", {}) or {}
    wind = data.get("wind", {}) or {}

    prob_lluvia = _extraer_numero(precipitation.get("probability")) if isinstance(precipitation, dict) else None
    cantidad_lluvia = _extraer_numero(precipitation)
    viento = _extraer_numero(wind)

    tormenta = data.get("thunderstormProbability")
    nube = data.get("cloudCover")

    factor = 1.0
    motivos = []

    if "thunder" in texto or "tormenta" in texto:
        factor += 0.12
        motivos.append("posible tormenta")

    elif "rain" in texto or "lluv" in texto or "drizzle" in texto:
        factor += 0.06
        motivos.append("lluvia reportada")

    if prob_lluvia is not None and prob_lluvia >= 60:
        factor += 0.04
        motivos.append("probabilidad alta de precipitación")

    if cantidad_lluvia is not None and cantidad_lluvia > 0:
        factor += 0.03
        motivos.append("precipitación detectada")

    if viento is not None and viento >= 30:
        factor += 0.04
        motivos.append("viento considerable")

    if nube is not None:
        try:
            if int(nube) >= 80:
                factor += 0.01
                motivos.append("alta nubosidad")
        except (TypeError, ValueError):
            pass

    if factor > 1.18:
        factor = 1.18

    if not motivos:
        motivos.append("sin afectación climática importante")

    return round(factor, 2), ", ".join(motivos)


def obtener_clima_google(lat, lon):
    """
    Consulta Google Weather API para clima actual.
    Usa cache de 10 minutos.
    """

    api_key = _api_key_servidor()

    if not api_key:
        return {
            "disponible": False,
            "fuente": "Google Weather API",
            "desde_cache": False,
            "factor_clima": 1.0,
            "descripcion_clima": "no disponible",
            "temperatura": None,
            "humedad": None,
            "nubosidad": None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "No se configuró GOOGLE_MAPS_SERVER_API_KEY.",
        }

    cache_key = (
        "google_weather_actual:"
        f"{_redondear_coord(lat, 3)}:"
        f"{_redondear_coord(lon, 3)}"
    )

    cached = cache.get(cache_key)
    if cached:
        cached["desde_cache"] = True
        return cached

    url = "https://weather.googleapis.com/v1/currentConditions:lookup"

    params = {
        "key": api_key,
        "location.latitude": float(lat),
        "location.longitude": float(lon),
        "unitsSystem": "METRIC",
        "languageCode": "es-419",
    }

    try:
        response = requests.get(url, params=params, timeout=8)

        if response.status_code != 200:
            return {
                "disponible": False,
                "fuente": "Google Weather API",
                "desde_cache": False,
                "factor_clima": 1.0,
                "descripcion_clima": "no disponible",
                "temperatura": None,
                "humedad": None,
                "nubosidad": None,
                "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
                "mensaje": f"Google Weather API respondió {response.status_code}.",
            }

        data = response.json()

        weather_condition = data.get("weatherCondition", {}) or {}

        descripcion = (
            weather_condition.get("description", {}).get("text")
            or weather_condition.get("displayName", {}).get("text")
            or weather_condition.get("type")
            or "clima no especificado"
        )

        temperatura = _extraer_numero(data.get("temperature"))
        humedad = data.get("relativeHumidity")
        nubosidad = data.get("cloudCover")

        factor_clima, motivo_clima = _factor_clima_desde_respuesta(data)

        resultado = {
            "disponible": True,
            "fuente": "Google Weather API",
            "desde_cache": False,
            "factor_clima": factor_clima,
            "descripcion_clima": descripcion,
            "motivo_clima": motivo_clima,
            "temperatura": round(temperatura, 1) if temperatura is not None else None,
            "humedad": humedad,
            "nubosidad": nubosidad,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "Dato climático reportado por API.",
        }

        cache.set(cache_key, resultado, CACHE_GOOGLE_SEGUNDOS)
        return resultado

    except Exception as e:
        return {
            "disponible": False,
            "fuente": "Google Weather API",
            "desde_cache": False,
            "factor_clima": 1.0,
            "descripcion_clima": "no disponible",
            "temperatura": None,
            "humedad": None,
            "nubosidad": None,
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": f"No se pudo consultar clima: {str(e)}",
        }


def obtener_factores_google(lat_origen, lon_origen, lat_destino, lon_destino):
    """
    Devuelve tráfico y clima para alimentar el modelo predictivo.
    El clima se consulta en el punto medio de la ruta.
    """

    trafico = obtener_trafico_google(
        lat_origen,
        lon_origen,
        lat_destino,
        lon_destino
    )

    lat_media = (float(lat_origen) + float(lat_destino)) / 2
    lon_media = (float(lon_origen) + float(lon_destino)) / 2

    clima = obtener_clima_google(lat_media, lon_media)

    return {
        "trafico": trafico,
        "clima": clima,
    }

# ==========================================================
# GOOGLE ROUTES API - RESPALDO DE RUTA VEHICULAR
# ==========================================================

def decodificar_polyline(encoded):
    """
    Decodifica una polilínea encodedPolyline de Google.
    Devuelve coordenadas en formato [[lat, lon], [lat, lon], ...]
    """
    if not encoded:
        return []

    coords = []
    index = 0
    lat = 0
    lon = 0

    while index < len(encoded):
        result = 0
        shift = 0

        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break

        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        result = 0
        shift = 0

        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break

        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += dlng

        coords.append([lat / 1e5, lon / 1e5])

    return coords


def obtener_ruta_google_respaldo(lat_origen, lon_origen, lat_destino, lon_destino):
    """
    Calcula una ruta vehicular con Google Routes API.
    Se usa únicamente como respaldo cuando Dijkstra genera una ruta exagerada.
    """
    api_key = _api_key_servidor()

    if not api_key:
        return {
            "disponible": False,
            "mensaje": "No existe GOOGLE_MAPS_SERVER_API_KEY.",
            "coords": [],
            "distancia_km": None,
            "tiempo_min": None,
        }

    cache_key = (
        "google_routes_respaldo:"
        f"{_redondear_coord(lat_origen)}:{_redondear_coord(lon_origen)}:"
        f"{_redondear_coord(lat_destino)}:{_redondear_coord(lon_destino)}"
    )

    cacheado = cache.get(cache_key)
    if cacheado:
        cacheado["desde_cache"] = True
        return cacheado

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
    }

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(lat_origen),
                    "longitude": float(lon_origen),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(lat_destino),
                    "longitude": float(lon_destino),
                }
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "es-419",
        "units": "METRIC",
        "polylineQuality": "HIGH_QUALITY",
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code != 200:
            return {
                "disponible": False,
                "mensaje": f"Google Routes API respondió {response.status_code}: {response.text[:200]}",
                "coords": [],
                "distancia_km": None,
                "tiempo_min": None,
            }

        data = response.json()
        routes = data.get("routes", [])

        if not routes:
            return {
                "disponible": False,
                "mensaje": "Google no devolvió rutas.",
                "coords": [],
                "distancia_km": None,
                "tiempo_min": None,
            }

        route = routes[0]

        distancia_m = float(route.get("distanceMeters") or 0)
        duracion_seg = _duracion_google_a_segundos(route.get("duration"))

        encoded_polyline = (
            route.get("polyline", {}).get("encodedPolyline")
        )

        coords = decodificar_polyline(encoded_polyline)

        resultado = {
            "disponible": True,
            "fuente": "Google Routes API",
            "desde_cache": False,
            "coords": coords,
            "distancia_km": round(distancia_m / 1000, 3),
            "tiempo_min": round(duracion_seg / 60, 2),
            "consultado_en": timezone.localtime().strftime("%Y-%m-%d %H:%M"),
            "mensaje": "Ruta obtenida correctamente con Google Routes API.",
        }

        cache.set(cache_key, resultado, CACHE_GOOGLE_SEGUNDOS)

        return resultado

    except Exception as e:
        return {
            "disponible": False,
            "mensaje": f"Error consultando Google Routes API: {str(e)}",
            "coords": [],
            "distancia_km": None,
            "tiempo_min": None,
        }


def ruta_local_es_exagerada(distancia_local_km, tiempo_local_min, ruta_google):
    """
    Decide si la ruta de Dijkstra salió demasiado larga frente a Google.

    Reglas:
    - Google debe estar disponible.
    - La ruta local debe superar por 35% la distancia de Google.
    - Además debe haber al menos 0.50 km de diferencia.
    """
    if not ruta_google or not ruta_google.get("disponible"):
        return False

    distancia_google = ruta_google.get("distancia_km")
    tiempo_google = ruta_google.get("tiempo_min")

    if not distancia_google or not tiempo_google:
        return False

    if distancia_local_km <= 0 or tiempo_local_min <= 0:
        return False

    diferencia_km = distancia_local_km - distancia_google
    factor_distancia = distancia_local_km / distancia_google

    factor_tiempo = tiempo_local_min / tiempo_google if tiempo_google > 0 else 1

    if diferencia_km >= 0.50 and factor_distancia >= 1.35:
        return True

    if factor_tiempo >= 1.60 and diferencia_km >= 0.30:
        return True

    return False