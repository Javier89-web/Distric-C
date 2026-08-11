import hashlib
import math
import re
import requests

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


CACHE_GOOGLE_SEGUNDOS = 600  # 10 minutos
CACHE_ELEVACION_SEGUNDOS = 60 * 60 * 24 * 7  # 7 días: la topografía no cambia


def _distancia_haversine_m(lat1, lon1, lat2, lon2):
    """Distancia horizontal aproximada entre dos coordenadas, en metros."""
    radio = 6371000.0
    lat1_r = math.radians(float(lat1))
    lat2_r = math.radians(float(lat2))
    dlat = lat2_r - lat1_r
    dlon = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * radio * math.asin(min(1.0, math.sqrt(a)))


def _simplificar_path_elevacion(coords, max_puntos=80):
    """Reduce una geometría larga conservando inicio, fin y forma general."""
    validas = []
    for punto in coords or []:
        try:
            lat = float(punto[0])
            lon = float(punto[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        if validas and abs(validas[-1][0] - lat) < 1e-9 and abs(validas[-1][1] - lon) < 1e-9:
            continue
        validas.append((lat, lon))

    if len(validas) <= max_puntos:
        return validas
    if max_puntos < 2:
        return [validas[0], validas[-1]]

    ultimo = len(validas) - 1
    indices = sorted({round(i * ultimo / (max_puntos - 1)) for i in range(max_puntos)})
    return [validas[i] for i in indices]


def _resumir_perfil_elevacion(resultados, distancia_ruta_km=None):
    """Convierte muestras de Elevation API en una pendiente efectiva para la IA.

    La variable enviada al Random Forest es el ascenso acumulado dividido para
    la distancia horizontal total. Esto representa de forma conservadora cuánto
    esfuerzo de subida existe a lo largo de toda la alternativa.
    """
    muestras = []
    for item in resultados or []:
        ubicacion = item.get("location") or {}
        try:
            muestras.append({
                "lat": float(ubicacion.get("lat")),
                "lon": float(ubicacion.get("lng")),
                "elevacion_m": float(item.get("elevation")),
            })
        except (TypeError, ValueError):
            continue

    if len(muestras) < 2:
        return None

    elevaciones = [m["elevacion_m"] for m in muestras]
    ascenso = 0.0
    descenso = 0.0
    distancia_m = 0.0
    pendiente_max = 0.0

    for i in range(1, len(muestras)):
        anterior = muestras[i - 1]
        actual = muestras[i]
        horizontal = _distancia_haversine_m(
            anterior["lat"], anterior["lon"], actual["lat"], actual["lon"]
        )
        if horizontal < 1.0:
            continue
        distancia_m += horizontal
        delta = elevaciones[i] - elevaciones[i - 1]
        # Cambios menores a 25 cm suelen ser ruido de interpolación y no afectan
        # de forma material el consumo en una ruta vehicular.
        if abs(delta) < 0.25:
            continue
        if delta > 0:
            ascenso += delta
            pendiente_local = min((delta / horizontal) * 100.0, 30.0)
            pendiente_max = max(pendiente_max, pendiente_local)
        else:
            descenso += abs(delta)

    distancia_referencia_m = distancia_m
    try:
        distancia_modelo = float(distancia_ruta_km or 0) * 1000.0
        if distancia_modelo > 0:
            distancia_referencia_m = distancia_modelo
    except (TypeError, ValueError):
        pass

    if distancia_referencia_m <= 0:
        return None

    pendiente_efectiva = min(max((ascenso / distancia_referencia_m) * 100.0, 0.0), 12.0)
    return {
        "pendiente_pct_ia": round(pendiente_efectiva, 4),
        "ascenso_acumulado_m": round(ascenso, 2),
        "descenso_acumulado_m": round(descenso, 2),
        "pendiente_maxima_pct": round(pendiente_max, 2),
        "elevacion_inicio_m": round(elevaciones[0], 2),
        "elevacion_fin_m": round(elevaciones[-1], 2),
        "muestras": len(muestras),
    }


def obtener_topografia_ruta_google(coords, distancia_ruta_km=None):
    """Obtiene Elevation API para una alternativa sin exponer datos en la UI.

    Si Google no está disponible, devuelve pendiente 0 y la ruta continúa con
    el cálculo actual. La consulta se hace una sola vez por geometría y se cachea.
    """
    api_key = _api_key_servidor()
    if not api_key:
        return {
            "disponible": False,
            "api_disponible": False,
            "fuente": "Google Maps Elevation API",
            "pendiente_pct_ia": 0.0,
            "mensaje": "No se configuró GOOGLE_MAPS_SERVER_API_KEY.",
        }

    path = _simplificar_path_elevacion(coords, max_puntos=80)
    if len(path) < 2:
        return {
            "disponible": False,
            "api_disponible": False,
            "fuente": "Google Maps Elevation API",
            "pendiente_pct_ia": 0.0,
            "mensaje": "La geometría de la ruta no contiene suficientes puntos.",
        }

    try:
        km = max(float(distancia_ruta_km or 0), 0.0)
    except (TypeError, ValueError):
        km = 0.0
    muestras = max(24, min(96, int(round(24 + km * 8))))

    firma = ";".join(f"{lat:.5f},{lon:.5f}" for lat, lon in path)
    digest = hashlib.sha1(f"{firma}|{muestras}".encode("utf-8")).hexdigest()
    cache_key = f"google_elevation_path:{digest}"
    cached = cache.get(cache_key)
    if cached:
        resultado = dict(cached)
        resultado["desde_cache"] = True
        return resultado

    path_param = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in path)
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/elevation/json",
            params={"path": path_param, "samples": muestras, "key": api_key},
            timeout=10,
        )
        if response.status_code != 200:
            return {
                "disponible": False,
                "api_disponible": False,
                "fuente": "Google Maps Elevation API",
                "pendiente_pct_ia": 0.0,
                "mensaje": f"Elevation API respondió HTTP {response.status_code}.",
            }

        data = response.json()
        if data.get("status") != "OK":
            return {
                "disponible": False,
                "api_disponible": False,
                "fuente": "Google Maps Elevation API",
                "pendiente_pct_ia": 0.0,
                "mensaje": (data.get("error_message") or f"Elevation API: {data.get('status', 'ERROR')}")[:250],
            }

        resumen = _resumir_perfil_elevacion(data.get("results", []), distancia_ruta_km=km)
        if not resumen:
            return {
                "disponible": False,
                "api_disponible": False,
                "fuente": "Google Maps Elevation API",
                "pendiente_pct_ia": 0.0,
                "mensaje": "Elevation API no devolvió un perfil utilizable.",
            }

        resultado = {
            "disponible": True,
            "api_disponible": True,
            "desde_cache": False,
            "fuente": "Google Maps Elevation API",
            "mensaje": "Topografía incorporada internamente al cálculo predictivo.",
            **resumen,
        }
        cache.set(cache_key, resultado, CACHE_ELEVACION_SEGUNDOS)
        return resultado
    except (requests.RequestException, ValueError) as exc:
        return {
            "disponible": False,
            "api_disponible": False,
            "fuente": "Google Maps Elevation API",
            "pendiente_pct_ia": 0.0,
            "mensaje": f"No se pudo consultar Elevation API: {exc}",
        }


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