"""Vistas del módulo predictivo de rutas y viajes por tramos.

Flujo principal:
1. El conductor selecciona origen y destino.
2. Random Forest predice el consumo de cada arista.
3. Dijkstra calcula hasta seis rutas sobre el grafo con pesos dinámicos.
4. El conductor elige una alternativa e inicia el seguimiento GPS.
5. Al finalizar el tramo registra los productos entregados.
6. La carga se reduce y el siguiente tramo parte desde el destino anterior.
"""
from __future__ import annotations

import json
import logging
import secrets
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from PIL import Image as PILImage, UnidentifiedImageError

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from .ia_predictiva import predecir_consumo_combustible, predecir_costos_tramos, resumen_modelo
from .models import (
    DetallePlanCarga,
    EntregaPlanCarga,
    EntregaTramoViaje,
    Lugarguardado,
    ParadaPlanCarga,
    PlanCarga,
    PrecioCombustible,
    PuntoGPSViaje,
    RendimientoVehiculoTipo,
    ReportePDFViaje,
    RutaOpcion,
    TramoViaje,
    UbicacionVehiculo,
    Usuario,
    Vehiculo,
    Viaje,
)
from .rutas_utils import (
    _peso_arista_grafo,
    _recortar_entre_proyecciones,
    calcular_metricas_ruta,
    candidatos_enganche_vial,
    construir_coords_ruta_visual,
    construir_geometria_ruta_ajustada,
    construir_grafo_con_costos,
    dijkstra,
    distancia_aprox_metros,
    k_mejores_rutas,
    metricas_avanzadas_ruta,
    metricas_parciales_enganche,
    obtener_index_tramos,
    penalizacion_enganche_min,
    seleccionar_mejor_enganche_ruta,
)
from .reportes_viaje import construir_pdf_viaje
from .respaldo_pdf_cloudinary import respaldar_pdf_viaje
from .servicios_contexto_ruta import buscar_lugares_google, obtener_factores_ruta
from .servicios_google import obtener_topografia_ruta_google


MAX_RUTAS = 6
MAX_RUTAS_GENERAL = 3
COLORES_RUTAS = [
    "#2563eb",
    "#d97706",
    "#0f766e",
    "#7c3aed",
    "#23262b",
    "#0891b2",
]
RADIO_LLEGADA_M = 120.0

logger = logging.getLogger(__name__)


def _decimal(valor, defecto="0") -> Decimal:
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(defecto)


def _float(valor, defecto=0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def _administrador_actual(request):
    """Devuelve el usuario administrador real de la sesión."""
    if request.session.get("usuario_tiporol") != "ADMINISTRADOR":
        return None
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    try:
        return Usuario.objects.get(
            id_usuario=usuario_id,
            tiporol="ADMINISTRADOR",
            activo=True,
        )
    except Usuario.DoesNotExist:
        return None


def _modo_admin_rutas(request):
    return bool(
        _administrador_actual(request)
        and request.session.get("ruta_admin_modo")
        and request.session.get("ruta_admin_usuario_id")
        and request.session.get("ruta_admin_vehiculo_id")
        and request.session.get("ruta_admin_plan_id")
    )


def _usuario_actual(request):
    """Usuario operativo del módulo de rutas.

    Para un conductor normal corresponde al usuario autenticado. Durante una
    prueba administrativa corresponde al conductor seleccionado, sin cambiar
    la identidad real del administrador guardada en la sesión.
    """
    if _modo_admin_rutas(request):
        try:
            return Usuario.objects.get(
                id_usuario=request.session.get("ruta_admin_usuario_id"),
                tiporol="USUARIO",
                activo=True,
            )
        except Usuario.DoesNotExist:
            return None

    if request.session.get("usuario_tiporol") == "ADMINISTRADOR":
        return None

    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    try:
        return Usuario.objects.get(id_usuario=usuario_id, activo=True)
    except Usuario.DoesNotExist:
        return None


def _vehiculo_usuario(usuario, request=None):
    if not usuario:
        return None
    consulta = Vehiculo.objects.filter(usuario=usuario)
    if request is not None and _modo_admin_rutas(request):
        consulta = consulta.filter(
            id_vehiculo=request.session.get("ruta_admin_vehiculo_id")
        )
    return consulta.first()


def _plan_ruta_usuario(vehiculo, request=None):
    """Obtiene la carga confirmada que debe utilizar la ruta."""
    if not vehiculo:
        return None

    consulta = PlanCarga.objects.filter(vehiculo=vehiculo)
    if request is not None and _modo_admin_rutas(request):
        return (
            consulta
            .filter(id_plan_carga=request.session.get("ruta_admin_plan_id"))
            .prefetch_related("detalles__producto")
            .first()
        )

    hoy = timezone.localdate()
    return (
        consulta
        .filter(
            estado__in=["CONFIRMADO", "EN_RUTA"],
            fecha_planificada__lte=hoy,
        )
        .prefetch_related("detalles__producto")
        .order_by("-fecha_planificada", "-id_plan_carga")
        .first()
    )


def _limpiar_modo_admin_rutas(request, limpiar_tramo=True):
    for clave in (
        "ruta_admin_modo",
        "ruta_admin_usuario_id",
        "ruta_admin_vehiculo_id",
        "ruta_admin_plan_id",
    ):
        request.session.pop(clave, None)
    if limpiar_tramo:
        for clave in ("viaje_activo_id", "tramo_planificado_id", "tramo_activo_id"):
            request.session.pop(clave, None)


def _snapshot_carga_plan(plan):
    snapshot = []
    if not plan:
        return snapshot
    for detalle in plan.detalles.select_related("producto").all():
        producto = detalle.producto
        cantidad = int(detalle.cantidad_actual or 0)
        if cantidad <= 0:
            continue
        snapshot.append({
            "detalle_id": detalle.id_detalle_plan_carga,
            "producto_id": producto.id_producto_carga,
            "producto_nombre": producto.nombre_producto,
            "marca_producto": producto.marca_producto or "",
            "presentacion_producto": producto.get_presentacion_producto_display(),
            "presentacion_descriptiva": producto.presentacion_descriptiva,
            "unidad_carga": producto.unidad_carga,
            "unidad_carga_plural": producto.unidad_carga_plural,
            "peso_unitario_kg": str(detalle.peso_unitario_kg),
            "cantidad_inicial": cantidad,
            "cantidad_actual": cantidad,
        })
    return snapshot


def _peso_snapshot_carga(snapshot):
    total = Decimal("0.00")
    for item in snapshot or []:
        total += _decimal(item.get("cantidad_actual")) * _decimal(item.get("peso_unitario_kg"))
    return total


def _contexto_modo_admin(request):
    if not _modo_admin_rutas(request):
        return {"modo_admin_rutas": False}
    return {
        "modo_admin_rutas": True,
        "administrador_rutas": _administrador_actual(request),
        "usuario_rutas": _usuario_actual(request),
        "salir_modo_admin_url": reverse("admin_salir_prueba_rutas"),
        "planificacion_admin_url": reverse("admin_planificacion_rutas"),
        "reportes_admin_url": reverse("admin_reportes_viajes"),
    }


def _render_ruta(request, plantilla, contexto=None):
    datos = dict(contexto or {})
    datos.update(_contexto_modo_admin(request))
    return render(request, plantilla, datos)


def _peso_vehiculo_kg(vehiculo) -> float:
    return max(_float(vehiculo.peso_auto) * 1000.0, 0.0)


def _nombre_origen(lat, lon, nombre=None):
    if nombre and str(nombre).strip():
        return str(nombre).strip()[:250]
    return f"Punto de inicio ({float(lat):.5f}, {float(lon):.5f})"


def _nombre_destino(nombre, lat, lon):
    if nombre and str(nombre).strip():
        return str(nombre).strip()[:250]
    return f"Destino ({float(lat):.5f}, {float(lon):.5f})"


def _json_request(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _viaje_usuario(usuario, viaje_id, es_prueba=False):
    """Obtiene un viaje del conductor sin mezclar pruebas administrativas.

    Los viajes de prueba pertenecen técnicamente al conductor seleccionado para
    poder reutilizar el flujo operativo, pero solo son accesibles mientras el
    administrador mantiene activo el modo de simulación.
    """
    try:
        return Viaje.objects.get(
            id_viaje=viaje_id,
            usuario=usuario,
            es_prueba_administrativa=bool(es_prueba),
        )
    except (Viaje.DoesNotExist, TypeError, ValueError):
        return None


def _tramo_usuario(usuario, tramo_id, es_prueba=False):
    try:
        return (
            TramoViaje.objects
            .select_related("viaje", "viaje__vehiculo", "viaje__plan_carga", "ruta_seleccionada")
            .get(
                id_tramo_viaje=tramo_id,
                viaje__usuario=usuario,
                viaje__es_prueba_administrativa=bool(es_prueba),
            )
        )
    except (TramoViaje.DoesNotExist, TypeError, ValueError):
        return None


def _precio_litro(vehiculo) -> Decimal:
    precio = PrecioCombustible.objects.filter(
        tipo=vehiculo.tipocombustible_vehiculo
    ).order_by('-id_precio').first()
    return _decimal(precio.precio_por_litro if precio else 0)


def _rendimiento(vehiculo) -> float:
    rendimiento = RendimientoVehiculoTipo.objects.filter(tipo=vehiculo.tipovehiculo_vehiculo).first()
    return max(_float(rendimiento.km_l_promedio if rendimiento else 0), 0.0)


def _actualizar_totales_viaje(viaje):
    viaje.recalcular_totales()


def _ultimo_punto_y_distancia(tramo):
    punto = tramo.puntos_gps.order_by("-fecha_hora").first()
    distancia = (
        float(punto.distancia_destino_m)
        if punto and punto.distancia_destino_m is not None
        else None
    )
    return punto, distancia


def _clave_modo_prueba():
    return str(getattr(settings, "RUTAS_MODO_PRUEBA_CLAVE", "") or "")


def _modo_prueba_habilitado(request):
    """Permite omitir GPS únicamente al administrador en modo de rutas.

    La clave se obtiene de RUTAS_MODO_PRUEBA_CLAVE para no exponerla en el
    repositorio. Un usuario normal nunca recibe ni puede usar esta opción.
    """
    return bool(
        _administrador_actual(request)
        and _modo_admin_rutas(request)
        and _clave_modo_prueba()
    )


def _datos_origen_siguiente_tramo(ultimo, usar_gps=True):
    """Obtiene el origen correcto para continuar el viaje.

    En operación normal se utiliza la última posición GPS registrada. Cuando
    ``usar_gps`` es ``False`` —modo de prueba temporal— el origen se fuerza al
    destino B del tramo completado. Así la prueba de B → C nunca vuelve al
    punto A aunque existan puntos GPS antiguos del recorrido anterior.
    """
    if usar_gps:
        punto = ultimo.puntos_gps.order_by("-fecha_hora").first()
        if punto:
            return {
                "lat": punto.latitud,
                "lon": punto.longitud,
                "nombre": "Ubicación actual del vehículo",
                "fuente": "GPS",
            }

    return {
        "lat": ultimo.destino_latitud,
        "lon": ultimo.destino_longitud,
        "nombre": ultimo.destino_nombre or "Destino anterior",
        "fuente": "DESTINO_ANTERIOR_PRUEBA" if not usar_gps else "DESTINO_ANTERIOR",
    }


def _redireccion_siguiente_ruta(viaje, ultimo):
    origen = _datos_origen_siguiente_tramo(ultimo)
    query = urlencode({
        "viaje": viaje.id_viaje,
        "origen_lat": str(origen["lat"]),
        "origen_lon": str(origen["lon"]),
        "origen_nombre": origen["nombre"],
        "origen_fuente": origen["fuente"],
    })
    return redirect(f"{reverse('buscarlugares')}?{query}")


# =============================================================================
# BÚSQUEDA Y SELECCIÓN DE PUNTOS
# =============================================================================

def buscarlugares(request):
    usuario = _usuario_actual(request)
    if not usuario:
        if _administrador_actual(request):
            messages.info(request, "Selecciona primero un conductor, su vehículo y la carga para iniciar una prueba.")
            return redirect("admin_planificacion_rutas")
        messages.error(request, "Debes iniciar sesión.")
        return redirect("login")

    vehiculo = _vehiculo_usuario(usuario, request)
    if not vehiculo:
        messages.error(request, "Necesitas un vehículo asignado antes de generar rutas.")
        return redirect("admin_planificacion_rutas" if _administrador_actual(request) else "listadovehiculo")

    viaje_id = request.GET.get("viaje")
    viaje = _viaje_usuario(usuario, viaje_id, es_prueba=_modo_admin_rutas(request)) if viaje_id else None

    origen_lat = request.GET.get("origen_lat")
    origen_lon = request.GET.get("origen_lon")
    origen_nombre = request.GET.get("origen_nombre", "")

    if viaje and (origen_lat is None or origen_lon is None):
        ultimo = viaje.tramos.filter(estado="COMPLETADO").order_by("-orden").first()
        if ultimo:
            origen = _datos_origen_siguiente_tramo(ultimo)
            origen_lat = str(origen["lat"])
            origen_lon = str(origen["lon"])
            origen_nombre = origen["nombre"]

    return _render_ruta(request, "usuario/mapas/buscarlugares.html", {
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "viaje_activo": viaje,
        "origen_lat": origen_lat or "",
        "origen_lon": origen_lon or "",
        "origen_nombre": origen_nombre,
    })


@require_GET
def api_buscar_destinos(request):
    usuario = _usuario_actual(request)
    if not usuario:
        return JsonResponse({"ok": False, "resultados": [], "mensaje": "Sesión no válida."}, status=401)

    consulta = (request.GET.get("q") or "").strip()
    lat = _float(request.GET.get("lat"), None)
    lon = _float(request.GET.get("lon"), None)
    resultado = buscar_lugares_google(consulta, lat=lat, lon=lon)
    return JsonResponse(resultado, status=200 if resultado.get("ok") else 400)



def ver_lugar(request, lat, lon):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    nombre = request.GET.get("nombre", "Ubicación seleccionada")
    return _render_ruta(request, "usuario/mapas/ver_lugar.html", {
        "lat": lat,
        "lon": lon,
        "nombre": nombre,
        "origen_lat": request.GET.get("origen_lat", ""),
        "origen_lon": request.GET.get("origen_lon", ""),
        "origen_nombre": request.GET.get("origen_nombre", ""),
        "viaje_id": request.GET.get("viaje", ""),
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })


@require_POST
def api_guardar_lugar(request):
    usuario = _usuario_actual(request)
    if not usuario:
        return JsonResponse({"ok": False, "mensaje": "Sesión no válida."}, status=401)

    datos = _json_request(request)
    lat = _float(datos.get("latitud"), None)
    lon = _float(datos.get("longitud"), None)
    nombre = str(datos.get("nombre") or "Lugar seleccionado").strip()[:900]

    if lat is None or lon is None:
        return JsonResponse({"ok": False, "mensaje": "Coordenadas no válidas."}, status=400)

    existente = Lugarguardado.objects.filter(
        usuario=usuario,
        latitud_Lugarguardado__range=(lat - 0.00002, lat + 0.00002),
        longitud_Lugarguardado__range=(lon - 0.00002, lon + 0.00002),
    ).first()

    if existente:
        existente.nombre_Lugarguardado = nombre
        existente.fecha_guardado = timezone.now()
        existente.save(update_fields=["nombre_Lugarguardado", "fecha_guardado"])
        lugar = existente
    else:
        lugar = Lugarguardado.objects.create(
            usuario=usuario,
            nombre_Lugarguardado=nombre,
            latitud_Lugarguardado=lat,
            longitud_Lugarguardado=lon,
        )

    return JsonResponse({
        "ok": True,
        "mensaje": "Destino guardado correctamente.",
        "lugar_id": lugar.id_Lugarguardado,
    })


@require_POST
def guardar_lugar(request, lat, lon, nombre):
    """Compatibilidad con la URL anterior, protegida como operación POST."""
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    Lugarguardado.objects.update_or_create(
        usuario=usuario,
        latitud_Lugarguardado=float(lat),
        longitud_Lugarguardado=float(lon),
        defaults={"nombre_Lugarguardado": nombre},
    )
    messages.success(request, "Lugar guardado correctamente.")
    return redirect("ver_lugar", lat=lat, lon=lon)


@require_POST
def eliminar_lugar(request, id):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    lugar = Lugarguardado.objects.filter(id_Lugarguardado=id, usuario=usuario).first()
    if not lugar:
        messages.error(request, "El lugar no existe o no te pertenece.")
    else:
        lugar.delete()
        messages.success(request, "Lugar eliminado correctamente.")
    return redirect("buscarlugares")


# =============================================================================
# GENERACIÓN PREDICTIVA DE RUTAS
# =============================================================================

def _sumar_prediccion_ruta(ruta_ids, predicciones_aristas):
    consumo_base = 0.0
    consumo_predicho = 0.0
    score = 0.0
    modelo = {}

    for u, v in zip(ruta_ids[:-1], ruta_ids[1:]):
        pred = predicciones_aristas.get((int(u), int(v)))
        if not pred:
            continue
        consumo_base += pred.consumo_base_l
        consumo_predicho += pred.consumo_predicho_l
        score += pred.costo_dijkstra
        modelo = pred.detalle

    return consumo_base, consumo_predicho, score, modelo


def _sumar_prediccion_enganche(enganche, predicciones_aristas):
    """Prorratea la predicción de los fragmentos de vía de los extremos."""
    parciales = metricas_parciales_enganche(enganche)
    consumo_base = 0.0
    consumo_predicho = 0.0
    score = 0.0
    modelo = {}
    for tramo, fraccion in parciales.get("tramos", []):
        pred = predicciones_aristas.get((int(tramo.origen_id), int(tramo.destino_id)))
        if not pred:
            continue
        fraccion = max(0.0, min(float(fraccion), 1.0))
        consumo_base += pred.consumo_base_l * fraccion
        consumo_predicho += pred.consumo_predicho_l * fraccion
        score += pred.costo_dijkstra * fraccion
        modelo = pred.detalle
    return consumo_base, consumo_predicho, score, modelo, parciales




def _filtrar_candidatos_enganche_general(candidatos, *, tolerancia_m=18.0, distancia_max_m=90.0):
    """Reduce los enganches de Tramos Generales a las calzadas realmente cercanas.

    El selector compartido permite explorar varias vías para encontrar una ruta. En una
    planificación completa eso puede provocar que un punto intermedio se proyecte sobre
    una calle paralela más lejana porque ofrece un costo menor. Aquí se conserva solo el
    grupo de aristas físicamente próximo al marcador. Es una regla exclusiva de Tramos
    Generales y no modifica el cálculo normal por tramo.
    """
    candidatos = sorted(
        list(candidatos or []),
        key=lambda item: (
            _float(item.get("distancia_ajuste_m"), 999999.0),
            _float(getattr(item.get("tramo"), "tiempo_base_min", 0.0), 0.0),
            int(getattr(item.get("tramo"), "pk", 0) or 0),
        ),
    )
    if not candidatos:
        return []

    distancia_minima = _float(candidatos[0].get("distancia_ajuste_m"), 999999.0)
    if distancia_minima > float(distancia_max_m):
        return []

    limite = min(float(distancia_max_m), distancia_minima + float(tolerancia_m))
    filtrados = [
        candidato for candidato in candidatos
        if _float(candidato.get("distancia_ajuste_m"), 999999.0) <= limite
    ]
    return filtrados[:10]


def _seleccionar_enganche_general_inicial(*, lat_origen, lon_origen, lat_destino, lon_destino, grafo):
    """Enganche seguro para el primer tramo de una planificación general.

    Prioriza la proximidad física del punto a la calzada antes del ahorro de tiempo.
    Evita que el primer cálculo salte a una vía paralela o a una rampa alejada.
    """
    origenes = _filtrar_candidatos_enganche_general(
        candidatos_enganche_vial(lat_origen, lon_origen, "ORIGEN", k=18)
    )
    destinos = _filtrar_candidatos_enganche_general(
        candidatos_enganche_vial(lat_destino, lon_destino, "DESTINO", k=18)
    )
    if not origenes or not destinos:
        return None

    mejor = None

    for origen in origenes:
        for destino in destinos:
            if origen["tramo"].pk != destino["tramo"].pk:
                continue
            if origen["fraccion_proyeccion"] > destino["fraccion_proyeccion"]:
                continue
            diferencia = destino["fraccion_proyeccion"] - origen["fraccion_proyeccion"]
            peso_arista = _peso_arista_grafo(
                grafo,
                origen["tramo"].origen_id,
                origen["tramo"].destino_id,
                origen["tramo"].tiempo_base_min,
            )
            costo = peso_arista * diferencia
            score = (
                costo
                + penalizacion_enganche_min(origen["distancia_ajuste_m"])
                + penalizacion_enganche_min(destino["distancia_ajuste_m"])
            )
            coords = _recortar_entre_proyecciones(
                origen["geometria_completa"], origen["proyeccion"], destino["proyeccion"]
            )
            candidato = {
                "ruta_directa": True,
                "ruta_directa_coords": coords,
                "fraccion_directa": diferencia,
                "tramo_directo": origen["tramo"],
                "nodo_origen": None,
                "nodo_destino": None,
                "origen": origen,
                "destino": destino,
                "costo_ruta_min": costo,
                "score": score,
                "enganche_origen_m": origen["distancia_ajuste_m"],
                "enganche_destino_m": destino["distancia_ajuste_m"],
            }
            if mejor is None or candidato["score"] < mejor["score"]:
                mejor = candidato

    for origen in origenes:
        for destino in destinos:
            ruta_tmp, costo_tmp = dijkstra(grafo, origen["nodo_red"], destino["nodo_red"])
            if not ruta_tmp:
                continue
            costo_origen = _peso_arista_grafo(
                grafo,
                origen["tramo"].origen_id,
                origen["tramo"].destino_id,
                origen["tramo"].tiempo_base_min,
            ) * origen["fraccion_tramo"]
            costo_destino = _peso_arista_grafo(
                grafo,
                destino["tramo"].origen_id,
                destino["tramo"].destino_id,
                destino["tramo"].tiempo_base_min,
            ) * destino["fraccion_tramo"]
            score = (
                costo_tmp
                + costo_origen
                + costo_destino
                + penalizacion_enganche_min(origen["distancia_ajuste_m"])
                + penalizacion_enganche_min(destino["distancia_ajuste_m"])
            )
            candidato = {
                "ruta_directa": False,
                "nodo_origen": origen["nodo_obj"],
                "nodo_destino": destino["nodo_obj"],
                "ruta_ids": ruta_tmp,
                "origen": origen,
                "destino": destino,
                "costo_ruta_min": costo_tmp + costo_origen + costo_destino,
                "score": score,
                "enganche_origen_m": origen["distancia_ajuste_m"],
                "enganche_destino_m": destino["distancia_ajuste_m"],
            }
            if candidato["nodo_origen"] is None or candidato["nodo_destino"] is None:
                continue
            if mejor is None or candidato["score"] < mejor["score"]:
                mejor = candidato

    return mejor


def _construir_geometria_general_segura(ruta_ids, enganche, tolerancia_empalme_m=6.0):
    """Construye la geometría del tramo sin crear conectores rectos artificiales.

    Los tres bloques (recorte de origen, camino Dijkstra y recorte de destino)
    deben tocarse físicamente. Si la red importada contiene una inconsistencia, se
    descarta esa alternativa en vez de dibujar una línea recta a través de una
    manzana.
    """
    if enganche.get("ruta_directa"):
        coords = [list(p) for p in enganche.get("ruta_directa_coords", [])]
        return coords if len(coords) >= 2 else []

    partes = [
        list(enganche["origen"].get("geometria_parcial", []) or []),
        list(construir_coords_ruta_visual(ruta_ids) or []),
        list(enganche["destino"].get("geometria_parcial", []) or []),
    ]
    partes = [parte for parte in partes if parte]
    if not partes:
        return []

    for anterior, siguiente in zip(partes[:-1], partes[1:]):
        if not anterior or not siguiente:
            continue
        salto = distancia_aprox_metros(
            anterior[-1][0], anterior[-1][1], siguiente[0][0], siguiente[0][1]
        )
        if salto > float(tolerancia_empalme_m):
            return []

    salida = []
    for parte in partes:
        for punto in parte:
            try:
                coord = [float(punto[0]), float(punto[1])]
            except (TypeError, ValueError, IndexError):
                continue
            if not salida or distancia_aprox_metros(
                salida[-1][0], salida[-1][1], coord[0], coord[1]
            ) > 0.35:
                salida.append(coord)
    return salida


def _geometria_general_valida(coords, origen_ajustado, destino_ajustado, distancia_km):
    """Comprueba extremos y longitud antes de aceptar una alternativa general."""
    if not coords or len(coords) < 2:
        return False
    if distancia_aprox_metros(coords[0][0], coords[0][1], origen_ajustado[0], origen_ajustado[1]) > 3.0:
        return False
    if distancia_aprox_metros(coords[-1][0], coords[-1][1], destino_ajustado[0], destino_ajustado[1]) > 3.0:
        return False

    longitud_m = 0.0
    for a, b in zip(coords[:-1], coords[1:]):
        longitud_m += distancia_aprox_metros(a[0], a[1], b[0], b[1])
    esperada_m = max(_float(distancia_km, 0.0) * 1000.0, 0.0)
    if esperada_m >= 80.0:
        relacion = longitud_m / esperada_m if esperada_m else 1.0
        if relacion < 0.60 or relacion > 1.45:
            return False
    return True


def _seleccionar_enganche_general_continuo(*, continuidad_origen, lat_destino, lon_destino, grafo):
    """Mantiene el mismo punto vial entre dos tramos consecutivos del plan general.

    Esta función es exclusiva de ``Tramos Generales``. No modifica el algoritmo
    compartido por el flujo normal. El destino ajustado del tramo anterior se
    reutiliza como origen físico del siguiente y, siempre que sea posible, se
    conserva exactamente la misma arista dirigida. Así se evita que un mismo
    punto intermedio sea proyectado dos veces sobre calzadas/rampas diferentes.
    """
    if not continuidad_origen:
        return None

    lat_origen = _float(continuidad_origen.get("lat"), None)
    lon_origen = _float(continuidad_origen.get("lon"), None)
    tramo_id = continuidad_origen.get("tramo_id")
    fraccion_previa = _float(continuidad_origen.get("fraccion_proyeccion"), None)
    if lat_origen is None or lon_origen is None or tramo_id is None:
        return None

    # El punto ya está sobre la red. Buscamos el mismo tramo dirigido que se usó
    # como llegada; de ese modo el siguiente segmento continúa legalmente hacia
    # el nodo final de esa arista antes de tomar otra vía.
    origenes = candidatos_enganche_vial(
        lat_origen,
        lon_origen,
        "ORIGEN",
        k=18,
        radio_max_m=80.0,
    )
    mismos = [
        candidato
        for candidato in origenes
        if int(candidato["tramo"].pk) == int(tramo_id)
    ]
    if mismos:
        origen = min(
            mismos,
            key=lambda candidato: (
                abs(_float(candidato.get("fraccion_proyeccion"), 0.0) - (fraccion_previa or 0.0)),
                _float(candidato.get("distancia_ajuste_m"), 999999.0),
            ),
        )
    else:
        # Fallback seguro: solo se acepta una arista cuyo punto ajustado esté
        # prácticamente en el mismo lugar físico. Nunca se salta a una calzada
        # paralela alejada solo por obtener una ruta más corta.
        candidatos_cercanos = []
        for candidato in origenes:
            punto = candidato.get("punto_ajustado") or []
            if len(punto) < 2:
                continue
            separacion = distancia_aprox_metros(lat_origen, lon_origen, punto[0], punto[1])
            if separacion <= 3.0:
                candidatos_cercanos.append((separacion, candidato))
        if not candidatos_cercanos:
            return None
        candidatos_cercanos.sort(key=lambda item: (item[0], _float(item[1]["tramo"].tiempo_base_min, 0.0)))
        origen = candidatos_cercanos[0][1]

    destinos = _filtrar_candidatos_enganche_general(
        candidatos_enganche_vial(
            lat_destino,
            lon_destino,
            "DESTINO",
            k=18,
        )
    )
    if not destinos:
        return None

    mejor = None

    # Caso directo: origen y destino caen en la misma arista y respetan el
    # sentido vehicular. Se replica únicamente la selección de enganche; el
    # resto del cálculo sigue usando las mismas funciones compartidas.
    for destino in destinos:
        if origen["tramo"].pk != destino["tramo"].pk:
            continue
        if origen["fraccion_proyeccion"] > destino["fraccion_proyeccion"]:
            continue
        diferencia = destino["fraccion_proyeccion"] - origen["fraccion_proyeccion"]
        peso_arista = _peso_arista_grafo(
            grafo,
            origen["tramo"].origen_id,
            origen["tramo"].destino_id,
            origen["tramo"].tiempo_base_min,
        )
        costo = peso_arista * diferencia
        score = (
            costo
            + penalizacion_enganche_min(origen["distancia_ajuste_m"])
            + penalizacion_enganche_min(destino["distancia_ajuste_m"])
        )
        coords = _recortar_entre_proyecciones(
            origen["geometria_completa"],
            origen["proyeccion"],
            destino["proyeccion"],
        )
        candidato = {
            "ruta_directa": True,
            "ruta_directa_coords": coords,
            "fraccion_directa": diferencia,
            "tramo_directo": origen["tramo"],
            "nodo_origen": None,
            "nodo_destino": None,
            "origen": origen,
            "destino": destino,
            "costo_ruta_min": costo,
            "score": score,
            "enganche_origen_m": origen["distancia_ajuste_m"],
            "enganche_destino_m": destino["distancia_ajuste_m"],
        }
        if mejor is None or candidato["score"] < mejor["score"]:
            mejor = candidato

    for destino in destinos:
        ruta_tmp, costo_tmp = dijkstra(
            grafo,
            origen["nodo_red"],
            destino["nodo_red"],
        )
        if not ruta_tmp:
            continue
        costo_origen = _peso_arista_grafo(
            grafo,
            origen["tramo"].origen_id,
            origen["tramo"].destino_id,
            origen["tramo"].tiempo_base_min,
        ) * origen["fraccion_tramo"]
        costo_destino = _peso_arista_grafo(
            grafo,
            destino["tramo"].origen_id,
            destino["tramo"].destino_id,
            destino["tramo"].tiempo_base_min,
        ) * destino["fraccion_tramo"]
        score = (
            costo_tmp
            + costo_origen
            + costo_destino
            + penalizacion_enganche_min(origen["distancia_ajuste_m"])
            + penalizacion_enganche_min(destino["distancia_ajuste_m"])
        )
        candidato = {
            "ruta_directa": False,
            "nodo_origen": origen["nodo_obj"],
            "nodo_destino": destino["nodo_obj"],
            "ruta_ids": ruta_tmp,
            "origen": origen,
            "destino": destino,
            "costo_ruta_min": costo_tmp + costo_origen + costo_destino,
            "score": score,
            "enganche_origen_m": origen["distancia_ajuste_m"],
            "enganche_destino_m": destino["distancia_ajuste_m"],
        }
        if candidato["nodo_origen"] is None or candidato["nodo_destino"] is None:
            continue
        if mejor is None or candidato["score"] < mejor["score"]:
            mejor = candidato

    return mejor


def _calcular_ruta_recomendada_general(
    *,
    vehiculo,
    plan,
    carga_actual_kg,
    lat_origen,
    lon_origen,
    lat_dest,
    lon_dest,
    continuidad_origen=None,
):
    """Calcula la alternativa recomendada para un tramo del plan general.

    Reutiliza el mismo grafo, Random Forest, tráfico, clima y topografía del
    flujo normal, pero devuelve únicamente la ruta con mejor score para poder
    construir todos los tramos de una jornada en una sola operación.
    """
    rendimiento = _rendimiento(vehiculo)
    if rendimiento <= 0:
        raise ValueError("No existe rendimiento configurado para este tipo de vehículo.")

    # Para el primer tramo se usa el punto seleccionado. En los siguientes,
    # el contexto parte del punto vial exacto donde terminó el tramo anterior.
    lat_origen_calculo = (
        _float(continuidad_origen.get("lat"), lat_origen)
        if continuidad_origen else lat_origen
    )
    lon_origen_calculo = (
        _float(continuidad_origen.get("lon"), lon_origen)
        if continuidad_origen else lon_origen
    )

    try:
        factores_google = obtener_factores_ruta(
            lat_origen=lat_origen_calculo,
            lon_origen=lon_origen_calculo,
            lat_destino=lat_dest,
            lon_destino=lon_dest,
        )
    except Exception as error:
        factores_google = {
            "trafico": {
                "disponible": True,
                "api_disponible": False,
                "fuente": "Estimación local de emergencia",
                "factor_trafico": 1.0,
                "descripcion_trafico": "tráfico neutral de respaldo",
                "mensaje": f"No se pudo consultar el contexto: {error}",
            },
            "clima": {
                "disponible": True,
                "api_disponible": False,
                "fuente": "Estimación climática neutral",
                "factor_clima": 1.0,
                "descripcion_clima": "condición neutral de respaldo",
                "mensaje": f"No se pudo consultar el contexto: {error}",
            },
        }

    tramos_red = list(obtener_index_tramos().values())
    predicciones_aristas = predecir_costos_tramos(
        tramos_red,
        vehiculo=vehiculo,
        carga_kg=float(carga_actual_kg),
        capacidad_kg=float(plan.capacidad_kg or 1),
        rendimiento_km_l=rendimiento,
        factores_google=factores_google,
        fecha_hora=timezone.localtime(),
    )

    grafo = construir_grafo_con_costos({
        clave: prediccion.costo_dijkstra
        for clave, prediccion in predicciones_aristas.items()
    })

    if continuidad_origen:
        enganche = _seleccionar_enganche_general_continuo(
            continuidad_origen=continuidad_origen,
            lat_destino=lat_dest,
            lon_destino=lon_dest,
            grafo=grafo,
        )
        if not enganche:
            raise ValueError(
                "No se pudo mantener la continuidad vial entre dos tramos generales. "
                "Ajusta ligeramente el punto intermedio y vuelve a calcular."
            )
    else:
        enganche = _seleccionar_enganche_general_inicial(
            lat_origen=lat_origen,
            lon_origen=lon_origen,
            lat_destino=lat_dest,
            lon_destino=lon_dest,
            grafo=grafo,
        )
        if not enganche:
            raise ValueError(
                "No se encontró una conexión vial segura para uno de los puntos. "
                "Coloca el marcador más cerca de la calzada y vuelve a calcular."
            )

    if enganche.get("ruta_directa"):
        rutas_candidatas = [([], float(enganche.get("costo_ruta_min", 0.0)))]
    else:
        rutas_candidatas = k_mejores_rutas(
            grafo,
            enganche["nodo_origen"].id_nodo,
            enganche["nodo_destino"].id_nodo,
            k=MAX_RUTAS_GENERAL,
            penalizacion_base=1.55,
            umbral_similitud=0.82,
        )
        if 0 < len(rutas_candidatas) < MAX_RUTAS_GENERAL:
            adicionales = k_mejores_rutas(
                grafo,
                enganche["nodo_origen"].id_nodo,
                enganche["nodo_destino"].id_nodo,
                k=MAX_RUTAS_GENERAL,
                penalizacion_base=1.55,
                umbral_similitud=0.95,
            )
            existentes = {tuple(ruta) for ruta, _ in rutas_candidatas}
            for ruta, costo in adicionales:
                firma = tuple(ruta)
                if firma not in existentes:
                    rutas_candidatas.append((ruta, costo))
                    existentes.add(firma)
                if len(rutas_candidatas) >= MAX_RUTAS_GENERAL:
                    break

    if not rutas_candidatas:
        raise ValueError("No se encontraron rutas transitables entre dos puntos del plan general.")

    parcial_base, parcial_predicho, parcial_score, parcial_modelo, parciales = (
        _sumar_prediccion_enganche(enganche, predicciones_aristas)
    )
    factor_trafico_ruta = _float(
        (factores_google.get("trafico", {}) or {}).get("factor_trafico"),
        1.0,
    )
    precio_litro = _precio_litro(vehiculo)
    detalles = []

    for ruta_ids, _ in rutas_candidatas:
        metricas = metricas_avanzadas_ruta(ruta_ids)
        metricas["distancia_km"] += parciales.get("distancia_km", 0.0)
        metricas["tiempo_min"] += parciales.get("tiempo_min", 0.0)
        metricas["tiempo_min"] *= factor_trafico_ruta
        metricas["velocidad_promedio_kmh"] = (
            metricas["distancia_km"] / metricas["tiempo_min"] * 60.0
            if metricas["tiempo_min"] > 0 else 0.0
        )

        consumo_base, consumo_predicho, score, modelo = _sumar_prediccion_ruta(
            ruta_ids,
            predicciones_aristas,
        )
        consumo_base += parcial_base
        consumo_predicho += parcial_predicho
        score += parcial_score
        if not modelo:
            modelo = parcial_modelo

        if enganche.get("ruta_directa"):
            tipo_via = enganche["tramo_directo"].tipo_via or "URBANA"
            distribucion = {tipo_via: 1}
            detenciones = 1
        else:
            tipo_via = metricas["tipo_via_dominante"]
            distribucion = metricas["distribucion_vias"]
            detenciones = metricas["detenciones_estimadas"]

        coords = _construir_geometria_general_segura(ruta_ids, enganche)
        if not _geometria_general_valida(
            coords,
            enganche["origen"]["punto_ajustado"],
            enganche["destino"]["punto_ajustado"],
            metricas["distancia_km"],
        ):
            continue

        topografia = obtener_topografia_ruta_google(
            coords,
            distancia_ruta_km=metricas["distancia_km"],
        )
        pendiente_pct = _float(topografia.get("pendiente_pct_ia"), 0.0)
        if topografia.get("disponible") and pendiente_pct > 0:
            argumentos_ia = {
                "distancia_km": metricas["distancia_km"],
                "tiempo_min": metricas["tiempo_min"],
                "consumo_base": consumo_base,
                "consumo_ajustado_peso": consumo_predicho,
                "factor_peso": 1.0,
                "factores_google": factores_google,
                "carga_kg": float(carga_actual_kg),
                "peso_vehiculo_kg": _peso_vehiculo_kg(vehiculo),
                "capacidad_kg": float(plan.capacidad_kg or 1),
                "cilindraje_l": _float(getattr(vehiculo, "cilindraje", 0), 0.0),
                "rendimiento_km_l": rendimiento,
                "tipo_via": tipo_via,
                "detenciones_estimadas": detenciones,
                "fecha_hora": timezone.localtime(),
            }
            referencia_plana = predecir_consumo_combustible(
                pendiente_pct=0.0,
                **argumentos_ia,
            )
            referencia_topografica = predecir_consumo_combustible(
                pendiente_pct=pendiente_pct,
                **argumentos_ia,
            )
            consumo_plano = _float(referencia_plana.get("consumo_predicho_litros"), 0.0)
            consumo_con_pendiente = _float(
                referencia_topografica.get("consumo_predicho_litros"),
                consumo_plano,
            )
            factor_topografico = 1.0
            if consumo_plano > 0:
                factor_topografico = consumo_con_pendiente / consumo_plano
            factor_topografico = min(max(factor_topografico, 1.0), 1.35)
            consumo_predicho *= factor_topografico
            score = (consumo_predicho * 60.0 * 0.65) + (metricas["tiempo_min"] * 0.35)
            topografia["factor_consumo_aplicado"] = round(factor_topografico, 5)
        else:
            topografia["factor_consumo_aplicado"] = 1.0

        detalles.append({
            "coords": coords,
            "distancia_km": metricas["distancia_km"],
            "tiempo_min": metricas["tiempo_min"],
            "velocidad_promedio_kmh": metricas["velocidad_promedio_kmh"],
            "detenciones_estimadas": detenciones,
            "tipo_via_dominante": tipo_via,
            "distribucion_vias": distribucion,
            "consumo_base": consumo_base,
            "consumo_predicho": consumo_predicho,
            "costo_estimado": consumo_predicho * float(precio_litro),
            "score": score,
            "modelo": modelo,
            "topografia": topografia,
        })

    if not detalles:
        raise ValueError("La red vial no produjo una geometría continua para uno de los tramos.")

    detalles.sort(key=lambda item: (item["score"], item["consumo_predicho"], item["tiempo_min"]))
    mejor = detalles[0]
    trafico = factores_google.get("trafico", {}) or {}
    clima = factores_google.get("clima", {}) or {}
    mejor["trafico"] = trafico
    mejor["clima"] = clima
    mejor["origen_ajustado"] = enganche["origen"]["punto_ajustado"]
    mejor["destino_ajustado"] = enganche["destino"]["punto_ajustado"]
    mejor["ajuste_origen_m"] = enganche.get("enganche_origen_m", 0)
    mejor["ajuste_destino_m"] = enganche.get("enganche_destino_m", 0)
    mejor["factores_google"] = factores_google
    # Metadato interno exclusivo del cálculo general. Permite que el siguiente
    # tramo arranque exactamente en la arista/punto donde terminó este.
    mejor["continuidad_destino"] = {
        "tramo_id": int(enganche["destino"]["tramo"].pk),
        "lat": float(enganche["destino"]["punto_ajustado"][0]),
        "lon": float(enganche["destino"]["punto_ajustado"][1]),
        "fraccion_proyeccion": float(enganche["destino"].get("fraccion_proyeccion", 0.0)),
    }
    return mejor


def _proyecciones_tramos_generales(tramos, servicio_por_parada_min=15.0):
    """Resume cuántas entregas caben aproximadamente en 3 h, 6 h y 1 día.

    No inventa una probabilidad estadística: usa el tiempo estimado de ruta y
    agrega una reserva operativa explícita de 15 minutos por parada.
    """
    tramos = list(tramos or [])
    acumulado = 0.0
    llegadas = []
    for tramo in tramos:
        acumulado += _float(tramo.tiempo_estimado_min)
        acumulado += float(servicio_por_parada_min)
        llegadas.append(acumulado)

    total = len(tramos)
    resultado = []
    for etiqueta, minutos in (("3 horas", 180), ("6 horas", 360), ("1 día", 1440)):
        alcanzados = sum(1 for valor in llegadas if valor <= minutos)
        porcentaje = (alcanzados / total * 100.0) if total else 0.0
        resultado.append({
            "etiqueta": etiqueta,
            "minutos": minutos,
            "destinos_alcanzados": alcanzados,
            "destinos_totales": total,
            "porcentaje": round(porcentaje, 1),
            "completo": bool(total and alcanzados == total),
        })
    return resultado, acumulado

def _crear_viaje_y_tramo(
    *,
    usuario,
    vehiculo,
    plan,
    origen_nombre,
    lat_origen,
    lon_origen,
    destino_nombre,
    lat_dest,
    lon_dest,
    viaje_id=None,
    es_prueba_administrativa=False,
    administrador_ejecutor=None,
    carga_actual_kg=None,
    snapshot_inicial=None,
):
    viaje = _viaje_usuario(usuario, viaje_id, es_prueba=es_prueba_administrativa) if viaje_id else None

    if viaje and viaje.estado not in {"PLANIFICADO", "EN_RUTA"}:
        viaje = None

    destino_guardado = Lugarguardado.objects.filter(
        usuario=usuario,
        latitud_Lugarguardado__range=(float(lat_dest) - 0.00003, float(lat_dest) + 0.00003),
        longitud_Lugarguardado__range=(float(lon_dest) - 0.00003, float(lon_dest) + 0.00003),
    ).first()

    if viaje:
        activo = viaje.tramos.filter(estado__in=["EN_RUTA", "PAUSADO", "PREPARADO"]).first()
        if activo:
            raise ValueError("Debes finalizar el tramo actual antes de generar otro.")
        viaje.tramos.filter(estado="PLANIFICADO").delete()
        carga_kg = (
            viaje.peso_carga_prueba_kg
            if viaje.es_prueba_administrativa
            else plan.peso_total_kg
        )
    else:
        snapshot = snapshot_inicial or []
        carga_kg = _decimal(
            carga_actual_kg
            if carga_actual_kg is not None
            else (_peso_snapshot_carga(snapshot) if es_prueba_administrativa else plan.peso_total_kg)
        )
        origen_obj = UbicacionVehiculo.objects.create(
            vehiculo=vehiculo,
            latitud=lat_origen,
            longitud=lon_origen,
        )
        viaje = Viaje.objects.create(
            usuario=usuario,
            vehiculo=vehiculo,
            origen=origen_obj,
            destino=destino_guardado,
            plan_carga=plan,
            es_prueba_administrativa=es_prueba_administrativa,
            administrador_ejecutor=administrador_ejecutor,
            carga_prueba_snapshot=snapshot if es_prueba_administrativa else [],
            estado="PLANIFICADO",
            origen_nombre=origen_nombre,
            origen_latitud=lat_origen,
            origen_longitud=lon_origen,
            destino_final_nombre=destino_nombre,
            destino_final_latitud=lat_dest,
            destino_final_longitud=lon_dest,
            carga_inicial_kg=carga_kg,
            carga_final_kg=carga_kg,
        )

    max_orden = viaje.tramos.aggregate(maximo=Max("orden"))["maximo"] or 0
    tramo = TramoViaje.objects.create(
        viaje=viaje,
        orden=max_orden + 1,
        estado="PLANIFICADO",
        origen_nombre=origen_nombre,
        origen_latitud=lat_origen,
        origen_longitud=lon_origen,
        destino_nombre=destino_nombre,
        destino_latitud=lat_dest,
        destino_longitud=lon_dest,
        carga_inicio_kg=carga_kg,
        carga_restante_kg=carga_kg,
    )

    viaje.destino = destino_guardado
    viaje.destino_final_nombre = destino_nombre
    viaje.destino_final_latitud = lat_dest
    viaje.destino_final_longitud = lon_dest
    viaje.save(update_fields=[
        "destino",
        "destino_final_nombre",
        "destino_final_latitud",
        "destino_final_longitud",
    ])
    return viaje, tramo


def rutas(request):
    usuario = _usuario_actual(request)
    if not usuario:
        if _administrador_actual(request):
            messages.info(request, "Selecciona una planificación administrativa antes de calcular rutas.")
            return redirect("admin_planificacion_rutas")
        return redirect("login")

    es_prueba_admin = _modo_admin_rutas(request)
    administrador_ejecutor = _administrador_actual(request) if es_prueba_admin else None
    vehiculo = _vehiculo_usuario(usuario, request)
    if not vehiculo:
        messages.error(request, "Necesitas un vehículo asignado para calcular rutas.")
        return redirect("admin_planificacion_rutas" if _administrador_actual(request) else "listadovehiculo")

    viaje_id = request.GET.get("viaje") or request.session.get("viaje_activo_id")
    viaje_existente = _viaje_usuario(usuario, viaje_id, es_prueba=es_prueba_admin) if viaje_id else None
    if viaje_existente and viaje_existente.estado in {"PLANIFICADO", "EN_RUTA"}:
        plan = viaje_existente.plan_carga
    else:
        viaje_existente = None
        viaje_id = None
        plan = _plan_ruta_usuario(vehiculo, request)

    if not plan or plan.vehiculo_id != vehiculo.id_vehiculo:
        messages.error(
            request,
            "Necesitas una carga asignada válida antes de iniciar una ruta.",
        )
        return redirect("admin_planificacion_rutas" if _administrador_actual(request) else "listadocarga")

    if viaje_existente and viaje_existente.es_prueba_administrativa:
        snapshot_carga = viaje_existente.carga_prueba_snapshot or []
        carga_actual_kg = viaje_existente.peso_carga_prueba_kg
    elif es_prueba_admin:
        snapshot_carga = _snapshot_carga_plan(plan)
        carga_actual_kg = _peso_snapshot_carga(snapshot_carga)
    else:
        snapshot_carga = []
        carga_actual_kg = plan.peso_total_kg

    if carga_actual_kg <= 0:
        messages.error(request, "La carga seleccionada no contiene productos disponibles para el recorrido.")
        return redirect("admin_planificacion_rutas" if _administrador_actual(request) else "listadocarga")

    lat_origen = _float(request.GET.get("origen_lat", request.GET.get("lat")), None)
    lon_origen = _float(request.GET.get("origen_lon", request.GET.get("lon")), None)
    lat_dest = _float(request.GET.get("destino_lat"), None)
    lon_dest = _float(request.GET.get("destino_lon"), None)

    if None in {lat_origen, lon_origen, lat_dest, lon_dest}:
        messages.error(request, "Selecciona correctamente el punto de inicio y el destino.")
        return redirect("buscarlugares")

    origen_nombre = _nombre_origen(lat_origen, lon_origen, request.GET.get("origen_nombre"))
    destino_nombre = _nombre_destino(request.GET.get("destino_nombre"), lat_dest, lon_dest)

    rendimiento = _rendimiento(vehiculo)
    if rendimiento <= 0:
        messages.error(request, "No existe rendimiento configurado para este tipo de vehículo.")
        return redirect("buscarlugares")

    try:
        factores_google = obtener_factores_ruta(
            lat_origen=lat_origen,
            lon_origen=lon_origen,
            lat_destino=lat_dest,
            lon_destino=lon_dest,
        )
    except Exception as error:
        factores_google = {
            "trafico": {
                "disponible": True,
                "api_disponible": False,
                "fuente": "Estimación local de emergencia",
                "factor_trafico": 1.0,
                "descripcion_trafico": "tráfico neutral de respaldo",
                "mensaje": f"No se pudo consultar el contexto: {error}",
            },
            "clima": {
                "disponible": True,
                "api_disponible": False,
                "fuente": "Estimación climática neutral",
                "factor_clima": 1.0,
                "descripcion_clima": "condición neutral de respaldo",
                "mensaje": f"No se pudo consultar el contexto: {error}",
            },
        }

    tramos_red = list(obtener_index_tramos().values())
    predicciones_aristas = predecir_costos_tramos(
        tramos_red,
        vehiculo=vehiculo,
        carga_kg=float(carga_actual_kg),
        capacidad_kg=float(plan.capacidad_kg or 1),
        rendimiento_km_l=rendimiento,
        factores_google=factores_google,
        fecha_hora=timezone.localtime(),
    )

    grafo = construir_grafo_con_costos({
        clave: prediccion.costo_dijkstra
        for clave, prediccion in predicciones_aristas.items()
    })

    enganche = seleccionar_mejor_enganche_ruta(
        lat_origen=lat_origen,
        lon_origen=lon_origen,
        lat_destino=lat_dest,
        lon_destino=lon_dest,
        grafo=grafo,
        k=24,
    )

    if not enganche:
        messages.error(request, "No se pudo conectar los puntos con la red vial de Latacunga.")
        return redirect("buscarlugares")

    if enganche.get("ruta_directa"):
        rutas_candidatas = [([], float(enganche.get("costo_ruta_min", 0.0)))]
    else:
        rutas_candidatas = k_mejores_rutas(
            grafo,
            enganche["nodo_origen"].id_nodo,
            enganche["nodo_destino"].id_nodo,
            k=MAX_RUTAS,
            penalizacion_base=1.55,
            umbral_similitud=0.82,
        )

        # Si la red urbana comparte obligatoriamente varios tramos, se relaja
        # únicamente la similitud; Yen sigue garantizando caminos sin ciclos.
        if 0 < len(rutas_candidatas) < MAX_RUTAS:
            adicionales = k_mejores_rutas(
                grafo,
                enganche["nodo_origen"].id_nodo,
                enganche["nodo_destino"].id_nodo,
                k=MAX_RUTAS,
                penalizacion_base=1.55,
                umbral_similitud=0.95,
            )
            existentes = {tuple(ruta) for ruta, _ in rutas_candidatas}
            for ruta, costo in adicionales:
                firma = tuple(ruta)
                if firma not in existentes:
                    rutas_candidatas.append((ruta, costo))
                    existentes.add(firma)
                if len(rutas_candidatas) >= MAX_RUTAS:
                    break

    if not rutas_candidatas:
        messages.error(request, "No se encontraron rutas transitables entre los puntos seleccionados.")
        return redirect("buscarlugares")

    origen_ajustado = enganche["origen"]["punto_ajustado"]
    destino_ajustado = enganche["destino"]["punto_ajustado"]

    try:
        viaje, tramo = _crear_viaje_y_tramo(
            usuario=usuario,
            vehiculo=vehiculo,
            plan=plan,
            origen_nombre=origen_nombre,
            lat_origen=origen_ajustado[0],
            lon_origen=origen_ajustado[1],
            destino_nombre=destino_nombre,
            lat_dest=destino_ajustado[0],
            lon_dest=destino_ajustado[1],
            viaje_id=viaje_id,
            es_prueba_administrativa=es_prueba_admin,
            administrador_ejecutor=administrador_ejecutor,
            carga_actual_kg=carga_actual_kg,
            snapshot_inicial=snapshot_carga,
        )
    except ValueError as error:
        messages.error(request, str(error))
        activo_id = request.session.get("tramo_activo_id")
        if activo_id:
            return redirect("recorrido_tramo", id_tramo=activo_id)
        return redirect("buscarlugares")

    precio_litro = _precio_litro(vehiculo)
    detalles = []
    parcial_base, parcial_predicho, parcial_score, parcial_modelo, parciales = (
        _sumar_prediccion_enganche(enganche, predicciones_aristas)
    )
    factor_trafico_ruta = _float(
        (factores_google.get("trafico", {}) or {}).get("factor_trafico"),
        1.0,
    )

    for ruta_ids, _ in rutas_candidatas:
        metricas = metricas_avanzadas_ruta(ruta_ids)
        metricas["distancia_km"] += parciales.get("distancia_km", 0.0)
        metricas["tiempo_min"] += parciales.get("tiempo_min", 0.0)
        metricas["tiempo_min"] *= factor_trafico_ruta
        metricas["velocidad_promedio_kmh"] = (
            metricas["distancia_km"] / metricas["tiempo_min"] * 60.0
            if metricas["tiempo_min"] > 0 else 0.0
        )
        consumo_base, consumo_predicho, score, modelo = _sumar_prediccion_ruta(
            ruta_ids,
            predicciones_aristas,
        )
        consumo_base += parcial_base
        consumo_predicho += parcial_predicho
        score += parcial_score
        if not modelo:
            modelo = parcial_modelo

        if enganche.get("ruta_directa"):
            tipo_via = enganche["tramo_directo"].tipo_via or "URBANA"
            distribucion = {tipo_via: 1}
            detenciones = 1
        else:
            tipo_via = metricas["tipo_via_dominante"]
            distribucion = metricas["distribucion_vias"]
            detenciones = metricas["detenciones_estimadas"]

        coords = construir_geometria_ruta_ajustada(ruta_ids, enganche)
        if len(coords) < 2:
            continue

        # La topografía se obtiene únicamente para las alternativas candidatas
        # (máximo seis), no para toda la red vial. De esta forma Elevation API
        # influye en la recomendación final sin disparar miles de consultas.
        topografia = obtener_topografia_ruta_google(
            coords,
            distancia_ruta_km=metricas["distancia_km"],
        )
        pendiente_pct = _float(topografia.get("pendiente_pct_ia"), 0.0)

        if topografia.get("disponible") and pendiente_pct > 0:
            # Aislamos el efecto aprendido de la pendiente comparando la misma
            # ruta con pendiente 0 frente a la pendiente real. El cociente se
            # aplica a la predicción acumulada por aristas, conservando el
            # comportamiento actual de Dijkstra/Random Forest y añadiendo solo
            # el componente topográfico.
            argumentos_ia = {
                "distancia_km": metricas["distancia_km"],
                "tiempo_min": metricas["tiempo_min"],
                "consumo_base": consumo_base,
                "consumo_ajustado_peso": consumo_predicho,
                "factor_peso": 1.0,
                "factores_google": factores_google,
                "carga_kg": float(carga_actual_kg),
                "peso_vehiculo_kg": _peso_vehiculo_kg(vehiculo),
                "capacidad_kg": float(plan.capacidad_kg or 1),
                "cilindraje_l": _float(getattr(vehiculo, "cilindraje", 0), 0.0),
                "rendimiento_km_l": rendimiento,
                "tipo_via": tipo_via,
                "detenciones_estimadas": detenciones,
                "fecha_hora": timezone.localtime(),
            }
            referencia_plana = predecir_consumo_combustible(
                pendiente_pct=0.0,
                **argumentos_ia,
            )
            referencia_topografica = predecir_consumo_combustible(
                pendiente_pct=pendiente_pct,
                **argumentos_ia,
            )
            consumo_plano = _float(referencia_plana.get("consumo_predicho_litros"), 0.0)
            consumo_con_pendiente = _float(
                referencia_topografica.get("consumo_predicho_litros"),
                consumo_plano,
            )
            factor_topografico = 1.0
            if consumo_plano > 0:
                factor_topografico = consumo_con_pendiente / consumo_plano
            # Protección conservadora frente a datos atípicos o ruido del DEM.
            factor_topografico = min(max(factor_topografico, 1.0), 1.35)
            consumo_predicho *= factor_topografico
            score = (consumo_predicho * 60.0 * 0.65) + (metricas["tiempo_min"] * 0.35)
            topografia["factor_consumo_aplicado"] = round(factor_topografico, 5)
        else:
            topografia["factor_consumo_aplicado"] = 1.0

        logger.info(
            "Topografia ruta: disponible=%s pendiente_ia=%.3f%% ascenso=%sm factor=%.4f",
            bool(topografia.get("disponible")),
            pendiente_pct,
            topografia.get("ascenso_acumulado_m", 0),
            _float(topografia.get("factor_consumo_aplicado"), 1.0),
        )

        detalles.append({
            "ruta_ids": ruta_ids,
            "coords": coords,
            "distancia_km": metricas["distancia_km"],
            "tiempo_min": metricas["tiempo_min"],
            "velocidad_promedio_kmh": metricas["velocidad_promedio_kmh"],
            "detenciones_estimadas": detenciones,
            "tipo_via_dominante": tipo_via,
            "distribucion_vias": distribucion,
            "consumo_base": consumo_base,
            "consumo_predicho": consumo_predicho,
            "costo_estimado": consumo_predicho * float(precio_litro),
            "score": score,
            "modelo": modelo,
            "topografia": topografia,
        })

    if not detalles:
        tramo.delete()
        if not viaje.tramos.exists():
            viaje.delete()
        messages.error(request, "La red vial no produjo una geometría continua para estos puntos.")
        return redirect("buscarlugares")

    # El modelo predictivo y el tiempo forman el costo definitivo.
    detalles.sort(key=lambda item: (item["score"], item["consumo_predicho"], item["tiempo_min"]))

    RutaOpcion.objects.filter(tramo=tramo).delete()
    rutas_json = []
    opciones = []
    score_minimo = detalles[0]["score"] if detalles else 1.0

    trafico = factores_google.get("trafico", {}) or {}
    clima = factores_google.get("clima", {}) or {}

    for indice, item in enumerate(detalles, start=1):
        es_recomendada = indice == 1
        diferencia_score = ((item["score"] / score_minimo) - 1.0) * 100 if score_minimo else 0.0
        detalle_prediccion = {
            "modelo": item["modelo"],
            "trafico": trafico,
            "clima": clima,
            # Se conserva para auditoría y reportes internos, pero no se muestra
            # en la pantalla de alternativas para mantener la interfaz limpia.
            "topografia": item.get("topografia", {}),
            "velocidad_promedio_kmh": round(item["velocidad_promedio_kmh"], 2),
            "detenciones_estimadas": item["detenciones_estimadas"],
            "tipo_via_dominante": item["tipo_via_dominante"],
            "distribucion_vias": item["distribucion_vias"],
            "diferencia_recomendada_pct": round(diferencia_score, 2),
            "peso_vehiculo_kg": round(_peso_vehiculo_kg(vehiculo), 2),
            "carga_kg": round(float(carga_actual_kg), 2),
            "ajuste_red_vial": {
                "origen_m": round(float(enganche.get("enganche_origen_m", 0)), 1),
                "destino_m": round(float(enganche.get("enganche_destino_m", 0)), 1),
                "origen_original": [lat_origen, lon_origen],
                "destino_original": [lat_dest, lon_dest],
                "origen_ajustado": origen_ajustado,
                "destino_ajustado": destino_ajustado,
            },
        }

        opcion = RutaOpcion.objects.create(
            viaje=viaje,
            tramo=tramo,
            tipo="RECOMENDADA" if es_recomendada else "ALTERNATIVA",
            indice_opcion=indice,
            es_recomendada=es_recomendada,
            tiempo_min=item["tiempo_min"],
            distancia_km=item["distancia_km"],
            consumo_litros=item["consumo_predicho"],
            costo_estimado=item["costo_estimado"],
            combustible_tipo=vehiculo.tipocombustible_vehiculo,
            geometria=item["coords"],
            fuente_ruta="Dijkstra + teoría de grafos + Random Forest",
            consumo_base_litros=_decimal(item["consumo_base"]),
            consumo_predicho_litros=_decimal(item["consumo_predicho"]),
            carga_inicio_kg=carga_actual_kg,
            score_optimizacion=_decimal(item["score"]),
            modelo_ia=item["modelo"].get("modelo", "Random Forest Regressor"),
            detalle_prediccion=detalle_prediccion,
        )
        rutas_json.append(item["coords"])
        opciones.append({
            "objeto": opcion,
            "indice": indice,
            "color": COLORES_RUTAS[(indice - 1) % len(COLORES_RUTAS)],
            "es_recomendada": es_recomendada,
            "distancia_km": item["distancia_km"],
            "tiempo_min": item["tiempo_min"],
            "consumo_base": item["consumo_base"],
            "consumo_predicho": item["consumo_predicho"],
            "costo_estimado": item["costo_estimado"],
            "diferencia_score": diferencia_score,
            "velocidad": item["velocidad_promedio_kmh"],
            "detenciones": item["detenciones_estimadas"],
            "tipo_via": item["tipo_via_dominante"],
            "modelo": item["modelo"],
        })

    request.session["viaje_activo_id"] = viaje.id_viaje
    request.session["tramo_planificado_id"] = tramo.id_tramo_viaje

    return _render_ruta(request, "usuario/mapas/rutas.html", {
        "viaje": viaje,
        "tramo": tramo,
        "vehiculo": vehiculo,
        "plan": plan,
        "opciones": opciones,
        "rutas_js": json.dumps(rutas_json),
        "origen_real": json.dumps({
            "latitud": origen_ajustado[0],
            "longitud": origen_ajustado[1],
            "nombre": origen_nombre,
        }),
        "destino_real": json.dumps({
            "latitud": destino_ajustado[0],
            "longitud": destino_ajustado[1],
            "nombre": destino_nombre,
        }),
        "ajuste_origen_m": enganche.get("enganche_origen_m", 0),
        "ajuste_destino_m": enganche.get("enganche_destino_m", 0),
        "factores_google": factores_google,
        "modelo_metadata": resumen_modelo(),
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })


@require_POST
def iniciar_ruta_seleccionada(request, id_ruta):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    try:
        opcion = (
            RutaOpcion.objects
            .select_related("tramo", "viaje")
            .get(id_ruta_opcion=id_ruta, viaje__usuario=usuario)
        )
    except RutaOpcion.DoesNotExist:
        messages.error(request, "La opción de ruta no existe.")
        return redirect("buscarlugares")

    tramo = opcion.tramo
    if not tramo or tramo.estado != "PLANIFICADO":
        messages.error(request, "Este tramo ya no puede iniciarse.")
        return redirect("buscarlugares")

    with transaction.atomic():
        RutaOpcion.objects.filter(tramo=tramo).update(seleccionada=False)
        opcion.seleccionada = True
        opcion.save(update_fields=["seleccionada"])

        detalle = opcion.detalle_prediccion or {}
        trafico = detalle.get("trafico", {}) or {}
        clima = detalle.get("clima", {}) or {}

        tramo.ruta_seleccionada = opcion
        tramo.estado = "PREPARADO"
        tramo.distancia_estimada_km = _decimal(opcion.distancia_km)
        tramo.tiempo_estimado_min = _decimal(opcion.tiempo_min)
        tramo.consumo_base_l = opcion.consumo_base_litros
        tramo.consumo_estimado_l = opcion.consumo_predicho_litros
        tramo.costo_estimado = _decimal(opcion.costo_estimado)
        tramo.trafico_factor = _decimal(trafico.get("factor_trafico", 1.0))
        tramo.trafico_descripcion = str(trafico.get("descripcion_trafico", "tráfico neutral de respaldo"))[:100]
        tramo.clima_factor = _decimal(clima.get("factor_clima", 1.0))
        tramo.clima_descripcion = str(clima.get("descripcion_clima", "condición neutral de respaldo"))[:150]
        tramo.temperatura_c = (
            _decimal(clima.get("temperatura"))
            if clima.get("temperatura") is not None else None
        )
        tramo.modelo_ia = opcion.modelo_ia
        tramo.detalle_prediccion = detalle
        tramo.geometria_ruta = opcion.geometria
        tramo.save()

    request.session["tramo_activo_id"] = tramo.id_tramo_viaje
    return redirect("recorrido_tramo", id_tramo=tramo.id_tramo_viaje)


@require_POST
def cancelar_generacion_ruta(request, id_tramo):
    usuario = _usuario_actual(request)
    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not tramo:
        return redirect("buscarlugares")

    viaje = tramo.viaje
    origen_lat = viaje.origen_latitud
    origen_lon = viaje.origen_longitud
    origen_nombre = viaje.origen_nombre

    if tramo.estado == "PLANIFICADO":
        tramo.delete()

    if not viaje.tramos.exists():
        viaje.delete()
        request.session.pop("viaje_activo_id", None)
        request.session.pop("tramo_planificado_id", None)

    query = urlencode({
        "origen_lat": str(origen_lat or ""),
        "origen_lon": str(origen_lon or ""),
        "origen_nombre": origen_nombre,
    })
    return redirect(f"{reverse('buscarlugares')}?{query}")


# =============================================================================
# SEGUIMIENTO GPS Y FINALIZACIÓN DEL TRAMO
# =============================================================================

def recorrido(request):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    tramo_id = request.GET.get("tramo") or request.session.get("tramo_activo_id")
    tramo = _tramo_usuario(usuario, tramo_id, es_prueba=_modo_admin_rutas(request))
    if not tramo:
        messages.error(request, "No existe un tramo preparado para iniciar.")
        return redirect("buscarlugares")
    return redirect("recorrido_tramo", id_tramo=tramo.id_tramo_viaje)


def recorrido_tramo(request, id_tramo):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request))
    if not tramo:
        messages.error(request, "El tramo no existe o no te pertenece.")
        return redirect("buscarlugares")

    if tramo.estado == "COMPLETADO":
        return redirect("resumen_tramo", id_tramo=tramo.id_tramo_viaje)

    if not tramo.ruta_seleccionada:
        messages.error(request, "Selecciona una ruta antes de iniciar el recorrido.")
        return redirect("buscarlugares")

    request.session["tramo_activo_id"] = tramo.id_tramo_viaje
    return _render_ruta(request, "usuario/mapas/recorrido.html", {
        "tramo": tramo,
        "viaje": tramo.viaje,
        "vehiculo": tramo.viaje.vehiculo,
        "ruta": tramo.ruta_seleccionada,
        "rutas_js": json.dumps([tramo.geometria_ruta]),
        "origen_real": json.dumps({
            "latitud": float(tramo.origen_latitud),
            "longitud": float(tramo.origen_longitud),
            "nombre": tramo.origen_nombre,
        }),
        "destino_real": json.dumps({
            "latitud": float(tramo.destino_latitud),
            "longitud": float(tramo.destino_longitud),
            "nombre": tramo.destino_nombre,
        }),
        "color_ruta": COLORES_RUTAS[(tramo.ruta_seleccionada.indice_opcion - 1) % len(COLORES_RUTAS)],
        "radio_llegada_m": int(RADIO_LLEGADA_M),
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })


@require_POST
def api_iniciar_tramo(request, id_tramo):
    usuario = _usuario_actual(request)
    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not tramo:
        return JsonResponse({"ok": False, "mensaje": "Tramo no encontrado."}, status=404)

    if tramo.estado not in {"PREPARADO", "PAUSADO", "EN_RUTA"}:
        return JsonResponse({"ok": False, "mensaje": "El tramo no está preparado."}, status=400)

    ahora = timezone.now()
    campos = ["estado"]
    tramo.estado = "EN_RUTA"
    if not tramo.fecha_inicio:
        tramo.fecha_inicio = ahora
        campos.append("fecha_inicio")
    tramo.save(update_fields=campos)

    viaje = tramo.viaje
    viaje.estado = "EN_RUTA"
    if not viaje.fecha_inicio:
        viaje.fecha_inicio = ahora
        viaje.save(update_fields=["estado", "fecha_inicio"])
    else:
        viaje.save(update_fields=["estado"])

    if (
        not viaje.es_prueba_administrativa
        and viaje.plan_carga
        and viaje.plan_carga.estado == "CONFIRMADO"
    ):
        viaje.plan_carga.estado = "EN_RUTA"
        viaje.plan_carga.save(update_fields=["estado", "fecha_actualizacion"])

    return JsonResponse({
        "ok": True,
        "mensaje": "Seguimiento GPS iniciado.",
        "estado": tramo.estado,
        "fecha_inicio": timezone.localtime(tramo.fecha_inicio).isoformat(),
    })


@require_POST
def api_pausar_tramo(request, id_tramo):
    usuario = _usuario_actual(request)
    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not tramo:
        return JsonResponse({"ok": False, "mensaje": "Tramo no encontrado."}, status=404)

    if tramo.estado == "EN_RUTA":
        tramo.estado = "PAUSADO"
        tramo.save(update_fields=["estado"])
    return JsonResponse({"ok": True, "mensaje": "Seguimiento pausado.", "estado": tramo.estado})


@require_POST
def api_registrar_ubicacion_tramo(request, id_tramo):
    usuario = _usuario_actual(request)
    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not tramo:
        return JsonResponse({"ok": False, "mensaje": "Tramo no encontrado."}, status=404)

    if tramo.estado != "EN_RUTA":
        return JsonResponse({"ok": False, "mensaje": "El seguimiento no está activo."}, status=409)

    datos = _json_request(request)
    lat = _float(datos.get("latitud"), None)
    lon = _float(datos.get("longitud"), None)
    if lat is None or lon is None:
        return JsonResponse({"ok": False, "mensaje": "Ubicación no válida."}, status=400)

    precision = _float(datos.get("precision"), None)
    velocidad = _float(datos.get("velocidad"), None)
    rumbo = _float(datos.get("rumbo"), None)
    ultimo = tramo.puntos_gps.order_by("-fecha_hora").first()
    distancia_anterior = 0.0

    if ultimo:
        distancia_anterior = distancia_aprox_metros(
            ultimo.latitud,
            ultimo.longitud,
            lat,
            lon,
        )
        # Evita saltos GPS irreales y ruido de menos de dos metros.
        if distancia_anterior < 2 or distancia_anterior > 1200:
            distancia_anterior = 0.0

    distancia_destino = distancia_aprox_metros(
        lat,
        lon,
        tramo.destino_latitud,
        tramo.destino_longitud,
    )

    PuntoGPSViaje.objects.create(
        tramo=tramo,
        latitud=lat,
        longitud=lon,
        precision_m=_decimal(precision) if precision is not None else None,
        velocidad_m_s=_decimal(velocidad) if velocidad is not None else None,
        rumbo_grados=_decimal(rumbo) if rumbo is not None else None,
        distancia_desde_anterior_m=_decimal(distancia_anterior),
        distancia_destino_m=_decimal(distancia_destino),
    )

    total_m = tramo.puntos_gps.aggregate(total=Sum("distancia_desde_anterior_m"))["total"] or Decimal("0")
    tramo.distancia_real_km = total_m / Decimal("1000")
    tramo.tiempo_real_min = tramo.duracion_actual_min
    tramo.save(update_fields=["distancia_real_km", "tiempo_real_min"])

    UbicacionVehiculo.objects.create(
        vehiculo=tramo.viaje.vehiculo,
        latitud=lat,
        longitud=lon,
    )

    return JsonResponse({
        "ok": True,
        "distancia_real_km": round(float(tramo.distancia_real_km), 3),
        "tiempo_real_min": round(float(tramo.tiempo_real_min), 2),
        "distancia_destino_m": round(float(distancia_destino), 1),
        "cerca_destino": distancia_destino <= RADIO_LLEGADA_M,
        "radio_llegada_m": RADIO_LLEGADA_M,
    })


def _validar_evidencia_entrega(archivo):
    if not archivo:
        return "Adjunte una fotografía de la entrega como evidencia obligatoria."

    nombre = (getattr(archivo, 'name', '') or '').lower()
    extensiones = ('.png', '.jpg', '.jpeg', '.webp')
    if not nombre.endswith(extensiones):
        return "La evidencia debe ser una imagen PNG, JPG, JPEG o WEBP."

    if getattr(archivo, 'size', 0) > 8 * 1024 * 1024:
        return "La evidencia no puede superar los 8 MB."

    tipo = (getattr(archivo, 'content_type', '') or '').lower()
    if tipo and tipo not in {'image/png', 'image/jpeg', 'image/webp'}:
        return "El archivo seleccionado no corresponde a una imagen válida."

    try:
        PILImage.open(archivo).verify()
        archivo.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        try:
            archivo.seek(0)
        except Exception:
            pass
        return "No se pudo validar la imagen de evidencia."

    return None


def _unidad_combustible_pdf(request):
    unidad = (request.GET.get('unidad') or 'LITROS').strip().upper()
    return 'GALONES' if unidad in {'GALON', 'GALONES', 'GAL'} else 'LITROS'


def _tramos_para_pdf(viaje):
    return list(
        viaje.tramos
        .select_related("ruta_seleccionada")
        .prefetch_related(
            "entregas_realizadas__detalle_carga__producto",
            "puntos_gps",
        )
        .order_by("orden")
    )


def _respaldar_pdf_seguro(viaje, contenido, unidad):
    try:
        return respaldar_pdf_viaje(
            viaje,
            contenido,
            unidad_combustible=unidad,
        )
    except Exception:
        logger.exception(
            "No se pudo respaldar en Cloudinary el PDF del viaje %s (%s).",
            viaje.id_viaje,
            unidad,
        )
        return None


def finalizar_tramo(request, id_tramo):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request))
    if not tramo:
        messages.error(request, "El tramo no existe o no te pertenece.")
        return redirect("historial")

    if tramo.estado not in {"EN_RUTA", "PAUSADO"}:
        messages.error(request, "Este tramo no puede finalizarse en su estado actual.")
        return redirect("recorrido_tramo", id_tramo=tramo.id_tramo_viaje)

    viaje = tramo.viaje
    plan = viaje.plan_carga
    es_prueba = viaje.es_prueba_administrativa
    errores = {}
    valores = {}
    nota_valor = ""

    filas_base = []
    detalles_por_id = {}
    if es_prueba:
        for item in viaje.carga_prueba_snapshot or []:
            cantidad = int(item.get("cantidad_actual") or 0)
            if cantidad <= 0:
                continue
            detalle_id = int(item.get("detalle_id"))
            filas_base.append({
                "detalle_id": detalle_id,
                "producto_nombre": item.get("producto_nombre") or "Producto",
                "marca_producto": item.get("marca_producto") or "",
                "presentacion_descriptiva": item.get("presentacion_descriptiva") or item.get("presentacion_producto") or "Unidad",
                "unidad_carga": item.get("unidad_carga") or "unidad",
                "unidad_carga_plural": item.get("unidad_carga_plural") or "unidades",
                "peso_unitario_kg": _decimal(item.get("peso_unitario_kg")),
                "cantidad_actual": cantidad,
                "snapshot_item": item,
            })
    elif plan:
        detalles = list(plan.detalles.select_related("producto").filter(cantidad_actual__gt=0))
        for detalle in detalles:
            detalles_por_id[detalle.id_detalle_plan_carga] = detalle
            filas_base.append({
                "detalle_id": detalle.id_detalle_plan_carga,
                "producto_nombre": detalle.producto.nombre_producto,
                "marca_producto": detalle.producto.marca_producto,
                "presentacion_descriptiva": detalle.producto.presentacion_descriptiva,
                "unidad_carga": detalle.producto.unidad_carga,
                "unidad_carga_plural": detalle.producto.unidad_carga_plural,
                "peso_unitario_kg": detalle.peso_unitario_kg,
                "cantidad_actual": detalle.cantidad_actual,
                "detalle": detalle,
            })

    if request.method == "POST":
        nota = request.POST.get("nota_finalizacion", "").strip()
        nota_valor = nota
        evidencia_entrega = request.FILES.get("evidencia_entrega")
        error_evidencia = _validar_evidencia_entrega(evidencia_entrega)
        if error_evidencia:
            errores["evidencia_entrega"] = error_evidencia

        total_entregado = Decimal("0.00")
        cantidades = {}

        for fila in filas_base:
            detalle_id = fila["detalle_id"]
            campo = f"entrega_{detalle_id}"
            texto = request.POST.get(campo, "0").strip()
            valores[campo] = texto
            try:
                cantidad = int(texto or 0)
            except ValueError:
                errores[campo] = "Ingresa una cantidad entera válida."
                continue

            if cantidad < 0:
                errores[campo] = "La cantidad no puede ser negativa."
            elif cantidad > fila["cantidad_actual"]:
                errores[campo] = f"Máximo disponible: {fila['cantidad_actual']}."
            else:
                cantidades[detalle_id] = cantidad
                total_entregado += Decimal(cantidad) * fila["peso_unitario_kg"]

        if total_entregado == 0 and not nota:
            errores["nota_finalizacion"] = "Explica por qué no se entregaron productos en este destino."

        if not errores:
            with transaction.atomic():
                tramo.entregas_realizadas.all().delete()

                if es_prueba:
                    snapshot = viaje.carga_prueba_snapshot or []
                    snapshot_por_id = {
                        int(item.get("detalle_id")): item
                        for item in snapshot
                        if item.get("detalle_id") is not None
                    }
                    detalles_originales = {
                        detalle.id_detalle_plan_carga: detalle
                        for detalle in DetallePlanCarga.objects.filter(
                            id_detalle_plan_carga__in=list(snapshot_por_id.keys())
                        ).select_related("producto")
                    }
                    for fila in filas_base:
                        detalle_id = fila["detalle_id"]
                        cantidad = cantidades.get(detalle_id, 0)
                        if cantidad <= 0:
                            continue
                        item = snapshot_por_id[detalle_id]
                        detalle_original = detalles_originales.get(detalle_id)
                        EntregaTramoViaje.objects.create(
                            tramo=tramo,
                            detalle_carga=detalle_original,
                            producto_nombre=fila["producto_nombre"],
                            marca_producto=fila["marca_producto"],
                            presentacion_producto=item.get("presentacion_producto") or "Unidad",
                            cantidad_entregada=cantidad,
                            peso_unitario_kg=fila["peso_unitario_kg"],
                        )
                        item["cantidad_actual"] = max(int(item.get("cantidad_actual") or 0) - cantidad, 0)
                    viaje.carga_prueba_snapshot = snapshot
                    viaje.save(update_fields=["carga_prueba_snapshot"])
                    carga_restante = _peso_snapshot_carga(snapshot)
                else:
                    for fila in filas_base:
                        detalle_id = fila["detalle_id"]
                        cantidad = cantidades.get(detalle_id, 0)
                        if cantidad <= 0:
                            continue
                        detalle = detalles_por_id[detalle_id]
                        EntregaTramoViaje.objects.create(
                            tramo=tramo,
                            detalle_carga=detalle,
                            producto_nombre=detalle.producto.nombre_producto,
                            marca_producto=detalle.producto.marca_producto,
                            presentacion_producto=detalle.producto.get_presentacion_producto_display(),
                            cantidad_entregada=cantidad,
                            peso_unitario_kg=detalle.peso_unitario_kg,
                        )
                        detalle.cantidad_actual -= cantidad
                        detalle.save(update_fields=["cantidad_actual"])
                    carga_restante = (
                        plan.peso_total_kg
                        if plan
                        else max(tramo.carga_inicio_kg - total_entregado, Decimal("0"))
                    )

                tramo.peso_entregado_kg = total_entregado
                tramo.carga_restante_kg = carga_restante
                tramo.fecha_fin = timezone.now()
                tramo.tiempo_real_min = tramo.duracion_actual_min
                tramo.estado = "COMPLETADO"
                tramo.nota_finalizacion = nota
                tramo.evidencia_entrega = evidencia_entrega
                tramo.consumo_real_l = None
                tramo.costo_real = None
                tramo.save()

                viaje.carga_final_kg = tramo.carga_restante_kg
                viaje.save(update_fields=["carga_final_kg"])
                _actualizar_totales_viaje(viaje)

            request.session.pop("tramo_activo_id", None)
            messages.success(request, "Tramo finalizado y carga actualizada correctamente.")
            return redirect("resumen_tramo", id_tramo=tramo.id_tramo_viaje)

    _, distancia_destino = _ultimo_punto_y_distancia(tramo)

    filas_detalles = []
    for fila in filas_base:
        campo = f"entrega_{fila['detalle_id']}"
        fila_render = dict(fila)
        fila_render.update({
            "campo": campo,
            "valor": valores.get(campo, "0"),
            "error": errores.get(campo, ""),
        })
        filas_detalles.append(fila_render)

    return _render_ruta(request, "usuario/mapas/finalizar_tramo.html", {
        "tramo": tramo,
        "plan": plan,
        "filas_detalles": filas_detalles,
        "errores": errores,
        "nota_valor": nota_valor,
        "distancia_destino_m": distancia_destino,
        "radio_llegada_m": int(RADIO_LLEGADA_M),
        **_contexto_modo_admin(request),
    })



def resumen_tramo(request, id_tramo):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")
    tramo = _tramo_usuario(usuario, id_tramo, es_prueba=_modo_admin_rutas(request))
    if not tramo:
        return redirect("historial")

    ultimo_punto, distancia_destino = _ultimo_punto_y_distancia(tramo)
    puede_nueva_ruta = tramo.viaje.estado in {"PLANIFICADO", "EN_RUTA"}
    puede_por_gps = bool(
        puede_nueva_ruta
        and ultimo_punto
        and distancia_destino is not None
        and distancia_destino <= RADIO_LLEGADA_M
    )
    return _render_ruta(request, "usuario/mapas/resumen_tramo.html", {
        "tramo": tramo,
        "viaje": tramo.viaje,
        "entregas": tramo.entregas_realizadas.all(),
        "puede_nueva_ruta": puede_nueva_ruta,
        "puede_nueva_ruta_gps": puede_por_gps,
        "distancia_destino_m": distancia_destino,
        "ultimo_punto_gps": ultimo_punto,
        "radio_llegada_m": int(RADIO_LLEGADA_M),
        "modo_prueba_habilitado": _modo_prueba_habilitado(request),
    })


@require_POST
def nueva_ruta_viaje(request, id_viaje):
    usuario = _usuario_actual(request)
    viaje = _viaje_usuario(usuario, id_viaje, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not viaje:
        return redirect("buscarlugares")

    activo = viaje.tramos.filter(estado__in=["EN_RUTA", "PAUSADO", "PREPARADO", "PLANIFICADO"]).first()
    if activo:
        messages.error(request, "Finaliza o cancela el tramo pendiente antes de crear otro.")
        return redirect("recorrido_tramo", id_tramo=activo.id_tramo_viaje)

    ultimo = viaje.tramos.filter(estado="COMPLETADO").order_by("-orden").first()
    if not ultimo:
        return redirect("buscarlugares")

    _, distancia_destino = _ultimo_punto_y_distancia(ultimo)
    if distancia_destino is None or distancia_destino > RADIO_LLEGADA_M:
        messages.error(
            request,
            "Para generar el siguiente tramo, el GPS debe confirmar que llegaste al destino anterior. "
            f"Radio permitido: {int(RADIO_LLEGADA_M)} m.",
        )
        return redirect("resumen_tramo", id_tramo=ultimo.id_tramo_viaje)

    return _redireccion_siguiente_ruta(viaje, ultimo)


@require_POST
def nueva_ruta_viaje_prueba(request, id_viaje):
    # Bypass GPS exclusivo del administrador. Aunque alguien conozca la URL,
    # un usuario normal no puede ejecutar este endpoint.
    if not _administrador_actual(request) or not _modo_admin_rutas(request):
        return JsonResponse({"ok": False, "mensaje": "Acción exclusiva del administrador."}, status=403)
    if not _modo_prueba_habilitado(request):
        return JsonResponse({"ok": False, "mensaje": "La autorización administrativa no está configurada."}, status=403)

    usuario = _usuario_actual(request)
    viaje = _viaje_usuario(usuario, id_viaje, es_prueba=True) if usuario else None
    if not viaje:
        return JsonResponse({"ok": False, "mensaje": "Viaje no válido."}, status=404)

    supplied = str((_json_request(request).get("clave") or ""))
    if not secrets.compare_digest(supplied, _clave_modo_prueba()):
        return JsonResponse({"ok": False, "mensaje": "Contraseña de prueba incorrecta."}, status=403)

    activo = viaje.tramos.filter(estado__in=["EN_RUTA", "PAUSADO", "PREPARADO", "PLANIFICADO"]).first()
    if activo:
        return JsonResponse({"ok": False, "mensaje": "Existe un tramo pendiente."}, status=409)

    ultimo = viaje.tramos.filter(estado="COMPLETADO").order_by("-orden").first()
    if not ultimo:
        return JsonResponse({"ok": False, "mensaje": "No existe un tramo completado."}, status=400)

    origen = _datos_origen_siguiente_tramo(ultimo, usar_gps=False)
    query = urlencode({
        "viaje": viaje.id_viaje,
        "origen_lat": str(origen["lat"]),
        "origen_lon": str(origen["lon"]),
        "origen_nombre": origen["nombre"],
        "origen_fuente": origen["fuente"],
    })
    return JsonResponse({"ok": True, "redirect": f"{reverse('buscarlugares')}?{query}"})



@require_POST
def finalizar_viaje(request, id_viaje):
    usuario = _usuario_actual(request)
    viaje = _viaje_usuario(usuario, id_viaje, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not viaje:
        return redirect("historial")

    if viaje.tramos.filter(estado__in=["EN_RUTA", "PAUSADO", "PREPARADO", "PLANIFICADO"]).exists():
        messages.error(request, "Existe un tramo pendiente. Finalízalo antes de cerrar el viaje.")
        return redirect("resumen_tramo", id_tramo=viaje.tramos.order_by("-orden").first().id_tramo_viaje)

    viaje.notas_cierre = request.POST.get("notas_cierre", "").strip()
    viaje.estado = "COMPLETADO"
    viaje.fecha_fin = timezone.now()
    _actualizar_totales_viaje(viaje)
    viaje.save(update_fields=["estado", "fecha_fin", "notas_cierre"])

    if viaje.plan_carga and not viaje.es_prueba_administrativa:
        viaje.plan_carga.estado = "COMPLETADO"
        viaje.plan_carga.save(update_fields=["estado", "fecha_actualizacion"])

    # El respaldo no debe impedir el cierre del viaje. Se genera una copia
    # canónica en litros y, si algo externo falla, el PDF puede reintentarse
    # más tarde desde el botón de reportes.
    respaldo_generado = None
    try:
        tramos_pdf = _tramos_para_pdf(viaje)
        contenido_pdf = construir_pdf_viaje(
            viaje,
            tramos_pdf,
            unidad_combustible="LITROS",
        )
        respaldo_generado = _respaldar_pdf_seguro(
            viaje,
            contenido_pdf,
            "LITROS",
        )
    except Exception:
        logger.exception(
            "No se pudo construir el respaldo PDF al finalizar el viaje %s.",
            viaje.id_viaje,
        )

    request.session.pop("viaje_activo_id", None)
    request.session.pop("tramo_planificado_id", None)
    request.session.pop("tramo_activo_id", None)
    messages.success(request, "Viaje finalizado. Se consolidaron todos los tramos.")
    if respaldo_generado:
        messages.success(request, "El informe PDF quedó respaldado en Cloudinary.")
    else:
        messages.warning(
            request,
            "El viaje se guardó correctamente, pero el respaldo PDF en Cloudinary quedó pendiente. "
            "Se volverá a intentar cuando descargues el informe.",
        )
    if viaje.es_prueba_administrativa and _administrador_actual(request):
        _limpiar_modo_admin_rutas(request, limpiar_tramo=False)
        return redirect("admin_detalle_viaje", id_viaje=viaje.id_viaje)
    return redirect("detalle_historial_viaje", id_viaje=viaje.id_viaje)


# =============================================================================
# HISTORIAL CONSOLIDADO
# =============================================================================

def historial(request):
    usuario = _usuario_actual(request)
    if not usuario:
        return redirect("login")

    viajes = (
        Viaje.objects
        .filter(usuario=usuario, es_prueba_administrativa=False)
        .select_related("vehiculo", "plan_carga")
        .prefetch_related(
            Prefetch(
                "tramos",
                queryset=TramoViaje.objects.order_by("orden").prefetch_related("entregas_realizadas"),
            )
        )
        .order_by("-fecha_creacion")
    )

    resumen = viajes.aggregate(
        distancia=Sum("distancia_real_total_km"),
        tiempo=Sum("tiempo_real_total_min"),
        combustible=Sum("consumo_estimado_total_l"),
        costo=Sum("costo_estimado_total"),
    )

    viaje_continuable = (
        viajes.filter(estado__in=["PLANIFICADO", "EN_RUTA"])
        .order_by("-fecha_creacion")
        .first()
    )
    continuacion_url = ""
    continuacion_texto = ""
    if viaje_continuable:
        pendiente = (
            viaje_continuable.tramos
            .filter(estado__in=["EN_RUTA", "PAUSADO", "PREPARADO", "PLANIFICADO"])
            .order_by("-orden")
            .first()
        )
        if pendiente and pendiente.estado in {"EN_RUTA", "PAUSADO", "PREPARADO"}:
            continuacion_url = reverse("recorrido_tramo", args=[pendiente.id_tramo_viaje])
            continuacion_texto = "Continuar recorrido"
        else:
            ultimo_completo = (
                viaje_continuable.tramos
                .filter(estado="COMPLETADO")
                .order_by("-orden")
                .first()
            )
            if ultimo_completo:
                continuacion_url = reverse("resumen_tramo", args=[ultimo_completo.id_tramo_viaje])
                continuacion_texto = "Volver al último tramo"

    return _render_ruta(request, "usuario/historial/historial.html", {
        "viajes": viajes,
        "resumen": resumen,
        "continuacion_url": continuacion_url,
        "continuacion_texto": continuacion_texto,
        "viaje_continuable": viaje_continuable,
    })


def detalle_historial_viaje(request, id_viaje):
    usuario = _usuario_actual(request)
    viaje = _viaje_usuario(usuario, id_viaje, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not viaje:
        messages.error(request, "El viaje no existe o no te pertenece.")
        return redirect("historial")

    tramos = (
        viaje.tramos
        .select_related("ruta_seleccionada")
        .prefetch_related(
            "entregas_realizadas__detalle_carga__producto",
            "puntos_gps",
        )
        .order_by("orden")
    )
    return _render_ruta(request, "usuario/historial/detalle_viaje.html", {
        "viaje": viaje,
        "tramos": tramos,
    })


@require_GET
def reporte_pdf_viaje(request, id_viaje):
    usuario = _usuario_actual(request)
    viaje = _viaje_usuario(usuario, id_viaje, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not viaje:
        messages.error(request, "El viaje no existe o no te pertenece.")
        return redirect("historial")

    tramos = _tramos_para_pdf(viaje)
    unidad = _unidad_combustible_pdf(request)
    contenido = construir_pdf_viaje(viaje, tramos, unidad_combustible=unidad)
    _respaldar_pdf_seguro(viaje, contenido, unidad)
    response = HttpResponse(contenido, content_type="application/pdf")
    sufijo = "galones" if unidad == "GALONES" else "litros"
    response["Content-Disposition"] = f'attachment; filename="viaje_{viaje.id_viaje}_distric_c_{sufijo}.pdf"'
    return response


@require_POST
def eliminar_viaje_historial(request, id_viaje):
    usuario = _usuario_actual(request)
    viaje = _viaje_usuario(usuario, id_viaje, es_prueba=_modo_admin_rutas(request)) if usuario else None
    if not viaje:
        messages.error(request, "El viaje no existe o no te pertenece.")
    elif viaje.estado == "EN_RUTA":
        messages.error(request, "No puedes eliminar un viaje que está en ejecución.")
    else:
        viaje.delete()
        messages.success(request, "Viaje eliminado del historial.")
    return redirect("historial")


# =============================================================================
# PLANIFICACIÓN Y REPORTES DE RUTAS - ADMINISTRADOR
# =============================================================================


def _planes_para_tramos_generales():
    """Cargas existentes utilizables exclusivamente por Tramos Generales.

    La selección de este módulo debe reutilizar los datos ya registrados en
    Vehiculo, Usuario y PlanCarga. No exige que el plan esté confirmado: un
    plan BORRADOR con productos también puede utilizarse para una simulación
    administrativa. Solo se excluyen los planes cancelados.
    """
    return (
        PlanCarga.objects
        .filter(
            vehiculo__usuario__isnull=False,
            vehiculo__usuario__activo=True,
            vehiculo__usuario__tiporol="USUARIO",
        )
        .exclude(estado="CANCELADO")
        .select_related("vehiculo", "vehiculo__usuario")
        .prefetch_related("detalles__producto")
        .distinct()
        .order_by("vehiculo__usuario__apellido_usuario", "-fecha_planificada", "-id_plan_carga")
    )


def admin_tramos_generales(request):
    administrador = _administrador_actual(request)
    if not administrador:
        messages.error(request, "No tienes permisos para acceder a los tramos generales.")
        return redirect("login")

    planes = []
    planes_json = {}

    # El selector Vehículo · conductor se alimenta directamente de los datos
    # existentes y NO depende de que exista una carga en un estado específico.
    # Así nunca desaparece un conductor/vehículo válido por un filtro de planes.
    vehiculos = list(
        Vehiculo.objects
        .filter(
            usuario__isnull=False,
            usuario__activo=True,
            usuario__tiporol="USUARIO",
        )
        .select_related("usuario")
        .order_by("usuario__apellido_usuario", "usuario__nombre_usuario", "matricula_vehiculo")
    )

    for plan in _planes_para_tramos_generales():
        detalles = list(
            plan.detalles.select_related("producto")
            .filter(cantidad_actual__gt=0)
            .order_by("producto__nombre_producto")
        )
        if not detalles:
            continue

        peso_total = plan.peso_total_kg
        if peso_total <= 0:
            continue

        vehiculo = plan.vehiculo
        usuario = vehiculo.usuario

        productos = []
        for detalle in detalles:
            producto = detalle.producto
            productos.append({
                "detalle_id": detalle.id_detalle_plan_carga,
                "producto": producto.nombre_producto,
                "marca": producto.marca_producto or "",
                "presentacion": producto.get_presentacion_producto_display(),
                "presentacion_resumen": producto.presentacion_resumen,
                "contenido_formateado": producto.contenido_unitario_formateado,
                "unidad_carga": producto.unidad_carga,
                "unidad_carga_plural": producto.unidad_carga_plural,
                "cantidad": int(detalle.cantidad_actual or 0),
                "peso_unitario_kg": float(detalle.peso_unitario_kg or 0),
                "peso_kg": float(detalle.peso_actual_kg or 0),
            })

        fila = {
            "plan": plan,
            "vehiculo": vehiculo,
            "usuario": usuario,
            "peso": peso_total,
            "productos": len(productos),
            "revisado": bool(plan.revisado_por_usuario),
        }
        planes.append(fila)

        planes_json[str(plan.id_plan_carga)] = {
            "id": plan.id_plan_carga,
            "vehiculo_id": vehiculo.id_vehiculo,
            "vehiculo": vehiculo.matricula_vehiculo,
            "modelo": vehiculo.modelo_vehiculo or "Sin modelo",
            "conductor": f"{usuario.nombre_usuario} {usuario.apellido_usuario}".strip(),
            "fecha": plan.fecha_planificada.strftime("%d/%m/%Y"),
            "estado": plan.get_estado_display(),
            "revisado": bool(plan.revisado_por_usuario),
            "peso_kg": float(peso_total),
            "productos": productos,
        }

    recientes = (
        Viaje.objects
        .filter(es_plan_general=True, administrador_ejecutor=administrador)
        .select_related("usuario", "vehiculo", "plan_carga")
        .annotate(cantidad_tramos=Count("tramos"))
        .order_by("-fecha_creacion")
    )

    plan_preseleccionado_id = str(request.GET.get("plan") or "").strip()
    if plan_preseleccionado_id not in planes_json:
        plan_preseleccionado_id = ""

    return render(request, "administrador/rutas/tramos_generales.html", {
        "vehiculos": vehiculos,
        "planes_disponibles": planes,
        "planes_json": json.dumps(planes_json),
        "plan_preseleccionado_id": plan_preseleccionado_id,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "recientes": recientes,
    })


@require_POST
def admin_calcular_tramos_generales(request):
    administrador = _administrador_actual(request)
    if not administrador:
        return redirect("login")

    plan_id = request.POST.get("plan_id")
    origen_lat = _float(request.POST.get("origen_lat"), None)
    origen_lon = _float(request.POST.get("origen_lon"), None)
    origen_nombre = (request.POST.get("origen_nombre") or "Punto 0").strip()[:250]

    if None in {origen_lat, origen_lon}:
        messages.error(request, "Selecciona el punto 0 de inicio en el mapa.")
        return redirect("admin_tramos_generales")

    try:
        plan = (
            PlanCarga.objects
            .select_related("vehiculo", "vehiculo__usuario")
            .prefetch_related("detalles__producto")
            .get(
                id_plan_carga=plan_id,
                vehiculo__usuario__isnull=False,
                vehiculo__usuario__activo=True,
                vehiculo__usuario__tiporol="USUARIO",
                estado__in=["BORRADOR", "LISTO", "CONFIRMADO", "EN_RUTA", "COMPLETADO"],
            )
        )
    except (PlanCarga.DoesNotExist, TypeError, ValueError):
        messages.error(request, "La carga seleccionada no es válida.")
        return redirect("admin_tramos_generales")

    detalles = list(
        plan.detalles.select_related("producto")
        .filter(cantidad_actual__gt=0)
        .order_by("producto__nombre_producto")
    )
    if not detalles or plan.peso_total_kg <= 0:
        messages.error(request, "La carga seleccionada no tiene productos disponibles.")
        return redirect("admin_tramos_generales")

    puntos_texto = (request.POST.get("puntos_paradas") or "").strip()
    try:
        puntos_recibidos = json.loads(puntos_texto) if puntos_texto else []
    except (json.JSONDecodeError, TypeError):
        puntos_recibidos = []

    puntos = []
    if isinstance(puntos_recibidos, list):
        for indice, fila in enumerate(puntos_recibidos, start=1):
            if not isinstance(fila, dict):
                continue
            lat = _float(fila.get("lat"), None)
            lon = _float(fila.get("lon"), None)
            if lat is None or lon is None:
                continue
            puntos.append({
                "numero": indice,
                "nombre": str(fila.get("nombre") or f"Punto {indice}")[:250],
                "lat": float(lat),
                "lon": float(lon),
            })

    if not puntos:
        messages.error(request, "Agrega al menos el punto 1 en el mapa antes de calcular.")
        return redirect("admin_tramos_generales")

    ajustes_por_punto = {}
    ajustes_texto = (request.POST.get("entregas_ajustadas") or "").strip()
    if ajustes_texto:
        try:
            ajustes_recibidos = json.loads(ajustes_texto)
        except (json.JSONDecodeError, TypeError):
            ajustes_recibidos = []
        if isinstance(ajustes_recibidos, list):
            for fila in ajustes_recibidos:
                if not isinstance(fila, dict):
                    continue
                try:
                    punto_numero = int(fila.get("punto_numero"))
                except (TypeError, ValueError):
                    continue
                mapa = {}
                entregas = fila.get("entregas", [])
                if isinstance(entregas, list):
                    for entrega in entregas:
                        try:
                            detalle_id = int(entrega.get("detalle_id"))
                            cantidad = int(entrega.get("cantidad"))
                        except (TypeError, ValueError, AttributeError):
                            continue
                        mapa[detalle_id] = cantidad
                ajustes_por_punto[punto_numero] = mapa

    notas_por_punto = {}
    notas_texto = (request.POST.get("notas_tramos") or "").strip()
    if notas_texto:
        try:
            notas_recibidas = json.loads(notas_texto)
        except (json.JSONDecodeError, TypeError):
            notas_recibidas = {}
        if isinstance(notas_recibidas, dict):
            for clave, valor in notas_recibidas.items():
                try:
                    punto_numero = int(clave)
                except (TypeError, ValueError):
                    continue
                notas_por_punto[punto_numero] = str(valor or "").strip()[:1000]

    vehiculo = plan.vehiculo
    usuario = vehiculo.usuario
    snapshot = _snapshot_carga_plan(plan)
    carga_inicial_kg = _peso_snapshot_carga(snapshot)
    cantidades_restantes = {
        int(item["detalle_id"]): int(item.get("cantidad_actual") or 0)
        for item in snapshot
    }
    detalles_por_id = {detalle.id_detalle_plan_carga: detalle for detalle in detalles}
    carga_actual_kg = carga_inicial_kg

    calculos = []
    punto_origen = {
        "nombre": origen_nombre or "Punto 0",
        "lat": float(origen_lat),
        "lon": float(origen_lon),
    }
    continuidad_origen = None

    try:
        for indice, punto_destino in enumerate(puntos, start=1):
            ruta = _calcular_ruta_recomendada_general(
                vehiculo=vehiculo,
                plan=plan,
                carga_actual_kg=carga_actual_kg,
                lat_origen=punto_origen["lat"],
                lon_origen=punto_origen["lon"],
                lat_dest=punto_destino["lat"],
                lon_dest=punto_destino["lon"],
                continuidad_origen=continuidad_origen,
            )

            # Protección adicional: dos geometrías consecutivas deben compartir
            # el mismo punto físico. Si no ocurre, se detiene el plan general en
            # lugar de guardar una ruta visualmente partida o cruzada.
            if calculos:
                fin_anterior = calculos[-1]["ruta"].get("coords", [])[-1]
                inicio_actual = (ruta.get("coords") or [None])[0]
                if not inicio_actual:
                    raise ValueError("Uno de los tramos generales no produjo una geometría válida.")
                separacion_empalme = distancia_aprox_metros(
                    fin_anterior[0],
                    fin_anterior[1],
                    inicio_actual[0],
                    inicio_actual[1],
                )
                if separacion_empalme > 3.0:
                    raise ValueError(
                        f"El empalme entre los tramos {indice - 2} y {indice - 1} quedó separado "
                        f"{separacion_empalme:.1f} m. Ajusta el punto intermedio para mantener "
                        "una ruta vehicular continua."
                    )
                # Unifica la coordenada compartida para que no exista ni siquiera
                # una separación visual por redondeo entre dos tramos consecutivos.
                ruta["coords"][0] = list(fin_anterior)
                ruta["origen_ajustado"] = list(fin_anterior)

            punto_numero = indice
            ajustes_punto = ajustes_por_punto.get(punto_numero, {})
            entregas = []
            peso_entregado = Decimal("0.00")

            for detalle in detalles:
                detalle_id = int(detalle.id_detalle_plan_carga)
                disponible = int(cantidades_restantes.get(detalle_id, 0))
                cantidad = ajustes_punto.get(detalle_id, 0)
                if cantidad < 0:
                    raise ValueError("Las cantidades a entregar no pueden ser negativas.")
                if cantidad > disponible:
                    raise ValueError(
                        f"La entrega de {detalle.producto.nombre_producto} en el punto {punto_numero} "
                        f"supera la cantidad disponible ({disponible})."
                    )

                if cantidad > 0:
                    producto = detalle.producto
                    peso_unitario = _decimal(detalle.peso_unitario_kg)
                    peso = Decimal(cantidad) * peso_unitario
                    peso_entregado += peso
                    entregas.append({
                        "detalle": detalles_por_id[detalle_id],
                        "producto_nombre": producto.nombre_producto,
                        "marca_producto": producto.marca_producto or "",
                        "presentacion_producto": producto.get_presentacion_producto_display(),
                        "cantidad": cantidad,
                        "peso_unitario_kg": peso_unitario,
                    })

                cantidades_restantes[detalle_id] = disponible - cantidad

            carga_restante = max(carga_actual_kg - peso_entregado, Decimal("0.00"))
            calculos.append({
                "orden": indice,
                "origen": punto_origen,
                "destino": punto_destino,
                "ruta": ruta,
                "carga_inicio_kg": carga_actual_kg,
                "peso_entregado_kg": peso_entregado,
                "carga_restante_kg": carga_restante,
                "entregas": entregas,
                "nota": notas_por_punto.get(punto_numero, ""),
            })
            carga_actual_kg = carga_restante
            # El nombre/coordenada original se conserva para la interfaz y el
            # reporte; el cálculo siguiente parte del punto vial ajustado.
            punto_origen = punto_destino
            continuidad_origen = ruta.get("continuidad_destino")

    except ValueError as error:
        messages.error(request, str(error))
        return redirect("admin_tramos_generales")
    except Exception:
        logger.exception("Error calculando tramos generales para el plan %s", plan.id_plan_carga)
        messages.error(request, "No se pudo completar el cálculo general. Revisa los puntos y la red vial e inténtalo nuevamente.")
        return redirect("admin_tramos_generales")

    if not calculos:
        messages.error(request, "No fue posible generar los tramos generales.")
        return redirect("admin_tramos_generales")

    # Última barrera antes de guardar: ningún plan nuevo puede persistir con
    # tramos flotantes, invertidos o ajustados demasiado lejos del marcador.
    fin_validado = None
    for item in calculos:
        ruta_validar = item.get("ruta", {})
        coords_validar = _coords_general_limpias(ruta_validar.get("coords", []))
        if len(coords_validar) < 2:
            messages.error(request, "Uno de los tramos no produjo una geometría vial válida.")
            return redirect("admin_tramos_generales")

        origen_ajustado = ruta_validar.get("origen_ajustado") or coords_validar[0]
        destino_ajustado = ruta_validar.get("destino_ajustado") or coords_validar[-1]
        if distancia_aprox_metros(
            coords_validar[0][0], coords_validar[0][1], origen_ajustado[0], origen_ajustado[1]
        ) > 3.0 or distancia_aprox_metros(
            coords_validar[-1][0], coords_validar[-1][1], destino_ajustado[0], destino_ajustado[1]
        ) > 3.0:
            messages.error(request, "La red vial generó un extremo inconsistente. Ajusta ligeramente el punto y vuelve a calcular.")
            return redirect("admin_tramos_generales")

        if fin_validado is not None and distancia_aprox_metros(
            fin_validado[0], fin_validado[1], coords_validar[0][0], coords_validar[0][1]
        ) > 3.0:
            messages.error(request, "La secuencia de tramos no quedó físicamente continua. Ajusta el punto intermedio y vuelve a calcular.")
            return redirect("admin_tramos_generales")

        destino_original = item.get("destino", {})
        if distancia_aprox_metros(
            float(destino_original.get("lat")),
            float(destino_original.get("lon")),
            float(destino_ajustado[0]),
            float(destino_ajustado[1]),
        ) > 95.0:
            messages.error(request, "Uno de los destinos quedó demasiado lejos de la calzada. Coloca el punto más cerca de una vía y vuelve a calcular.")
            return redirect("admin_tramos_generales")

        ruta_validar["coords"] = coords_validar
        fin_validado = list(coords_validar[-1])

    with transaction.atomic():
        ubicacion_origen = UbicacionVehiculo.objects.create(
            vehiculo=vehiculo,
            latitud=origen_lat,
            longitud=origen_lon,
        )
        ultimo_punto = puntos[-1]
        viaje = Viaje.objects.create(
            usuario=usuario,
            vehiculo=vehiculo,
            origen=ubicacion_origen,
            destino=None,
            plan_carga=plan,
            es_prueba_administrativa=True,
            es_plan_general=True,
            administrador_ejecutor=administrador,
            carga_prueba_snapshot=snapshot,
            estado="PLANIFICADO",
            origen_nombre=origen_nombre,
            origen_latitud=origen_lat,
            origen_longitud=origen_lon,
            destino_final_nombre=ultimo_punto["nombre"],
            destino_final_latitud=ultimo_punto["lat"],
            destino_final_longitud=ultimo_punto["lon"],
            carga_inicial_kg=carga_inicial_kg,
            carga_final_kg=carga_actual_kg,
            notas_cierre="Plan general calculado en secuencia con puntos seleccionados en el mapa.",
        )

        total_distancia = Decimal("0.000")
        total_tiempo = Decimal("0.00")
        total_consumo = Decimal("0.000")
        total_costo = Decimal("0.00")
        acumulado_operativo = 0.0

        for item in calculos:
            ruta = item["ruta"]
            trafico = ruta.get("trafico", {}) or {}
            clima = ruta.get("clima", {}) or {}
            modelo = ruta.get("modelo", {}) or {}
            acumulado_operativo += _float(ruta["tiempo_min"]) + 15.0
            detalle_prediccion = {
                "modelo": modelo,
                "trafico": trafico,
                "clima": clima,
                "topografia": ruta.get("topografia", {}),
                "velocidad_promedio_kmh": round(_float(ruta.get("velocidad_promedio_kmh")), 2),
                "detenciones_estimadas": ruta.get("detenciones_estimadas", 0),
                "tipo_via_dominante": ruta.get("tipo_via_dominante", "URBANA"),
                "distribucion_vias": ruta.get("distribucion_vias", {}),
                "peso_vehiculo_kg": round(_peso_vehiculo_kg(vehiculo), 2),
                "carga_kg": round(float(item["carga_inicio_kg"]), 2),
                "plan_general": {
                    "punto_origen": item["orden"] - 1,
                    "punto_destino": item["orden"],
                    "servicio_estimado_min": 15,
                    "acumulado_operativo_min": round(acumulado_operativo, 2),
                    "origen_original": [item["origen"]["lat"], item["origen"]["lon"]],
                    "destino_original": [item["destino"]["lat"], item["destino"]["lon"]],
                    "nota_planificacion": item["nota"],
                },
            }

            tramo = TramoViaje.objects.create(
                viaje=viaje,
                orden=item["orden"],
                estado="PREPARADO",
                origen_nombre=item["origen"]["nombre"],
                origen_latitud=ruta["origen_ajustado"][0],
                origen_longitud=ruta["origen_ajustado"][1],
                destino_nombre=item["destino"]["nombre"],
                destino_latitud=ruta["destino_ajustado"][0],
                destino_longitud=ruta["destino_ajustado"][1],
                carga_inicio_kg=item["carga_inicio_kg"],
                peso_entregado_kg=item["peso_entregado_kg"],
                carga_restante_kg=item["carga_restante_kg"],
                distancia_estimada_km=_decimal(ruta["distancia_km"]),
                tiempo_estimado_min=_decimal(ruta["tiempo_min"]),
                consumo_base_l=_decimal(ruta["consumo_base"]),
                consumo_estimado_l=_decimal(ruta["consumo_predicho"]),
                costo_estimado=_decimal(ruta["costo_estimado"]),
                trafico_factor=_decimal(trafico.get("factor_trafico", 1.0)),
                trafico_descripcion=str(trafico.get("descripcion_trafico", "tráfico neutral de respaldo"))[:100],
                clima_factor=_decimal(clima.get("factor_clima", 1.0)),
                clima_descripcion=str(clima.get("descripcion_clima", "condición neutral de respaldo"))[:150],
                temperatura_c=(
                    _decimal(clima.get("temperatura"))
                    if clima.get("temperatura") is not None else None
                ),
                modelo_ia=modelo.get("modelo", "Random Forest Regressor"),
                detalle_prediccion=detalle_prediccion,
                geometria_ruta=ruta["coords"],
                nota_finalizacion=item["nota"],
            )
            opcion = RutaOpcion.objects.create(
                viaje=viaje,
                tramo=tramo,
                tipo="RECOMENDADA",
                indice_opcion=1,
                es_recomendada=True,
                seleccionada=True,
                tiempo_min=ruta["tiempo_min"],
                distancia_km=ruta["distancia_km"],
                consumo_litros=ruta["consumo_predicho"],
                costo_estimado=ruta["costo_estimado"],
                combustible_tipo=vehiculo.tipocombustible_vehiculo,
                geometria=ruta["coords"],
                fuente_ruta="Dijkstra + teoría de grafos + Random Forest",
                consumo_base_litros=_decimal(ruta["consumo_base"]),
                consumo_predicho_litros=_decimal(ruta["consumo_predicho"]),
                carga_inicio_kg=item["carga_inicio_kg"],
                score_optimizacion=_decimal(ruta["score"]),
                modelo_ia=modelo.get("modelo", "Random Forest Regressor"),
                detalle_prediccion=detalle_prediccion,
            )
            tramo.ruta_seleccionada = opcion
            tramo.save(update_fields=["ruta_seleccionada"])

            for entrega in item["entregas"]:
                EntregaTramoViaje.objects.create(
                    tramo=tramo,
                    detalle_carga=entrega["detalle"],
                    producto_nombre=entrega["producto_nombre"],
                    marca_producto=entrega["marca_producto"],
                    presentacion_producto=entrega["presentacion_producto"],
                    cantidad_entregada=entrega["cantidad"],
                    peso_unitario_kg=entrega["peso_unitario_kg"],
                )

            total_distancia += _decimal(ruta["distancia_km"])
            total_tiempo += _decimal(ruta["tiempo_min"])
            total_consumo += _decimal(ruta["consumo_predicho"])
            total_costo += _decimal(ruta["costo_estimado"])

        viaje.distancia_estimada_total_km = total_distancia
        viaje.tiempo_estimado_total_min = total_tiempo
        viaje.consumo_estimado_total_l = total_consumo
        viaje.costo_estimado_total = total_costo
        viaje.carga_final_kg = carga_actual_kg
        viaje.save(update_fields=[
            "distancia_estimada_total_km",
            "tiempo_estimado_total_min",
            "consumo_estimado_total_l",
            "costo_estimado_total",
            "carga_final_kg",
        ])

    messages.success(request, "Tramos generales calculados en secuencia con la ruta recomendada de cada tramo.")
    return redirect("admin_detalle_tramos_generales", id_viaje=viaje.id_viaje)



def _coords_general_limpias(coords):
    """Convierte una geometría JSON almacenada en pares [lat, lon] válidos."""
    salida = []
    for punto in coords or []:
        try:
            lat = float(punto[0])
            lon = float(punto[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        actual = [lat, lon]
        if not salida or distancia_aprox_metros(
            salida[-1][0], salida[-1][1], actual[0], actual[1]
        ) > 0.35:
            salida.append(actual)
    return salida


def _rutas_generales_guardadas_continuas(tramos, tolerancia_m=8.0):
    """Valida y normaliza las geometrías guardadas de un plan general.

    Los cálculos antiguos podían conservar geometrías con extremos mal orientados
    o con un salto entre dos tramos. Esta función nunca inventa una recta: solo
    acepta la geometría si todos los tramos se tocan físicamente y sus extremos
    coinciden con los extremos viales almacenados.
    """
    rutas = []
    fin_anterior = None

    ordenes = [int(tramo.orden) for tramo in tramos]
    if ordenes and ordenes != list(range(1, len(ordenes) + 1)):
        return None

    for indice_tramo, tramo in enumerate(tramos):
        coords = _coords_general_limpias(tramo.geometria_ruta or [])
        if len(coords) < 2:
            return None

        origen = [float(tramo.origen_latitud), float(tramo.origen_longitud)]
        destino = [float(tramo.destino_latitud), float(tramo.destino_longitud)]

        directo = (
            distancia_aprox_metros(coords[0][0], coords[0][1], origen[0], origen[1])
            + distancia_aprox_metros(coords[-1][0], coords[-1][1], destino[0], destino[1])
        )
        inverso = (
            distancia_aprox_metros(coords[-1][0], coords[-1][1], origen[0], origen[1])
            + distancia_aprox_metros(coords[0][0], coords[0][1], destino[0], destino[1])
        )
        if inverso + 0.5 < directo:
            coords.reverse()

        if distancia_aprox_metros(coords[0][0], coords[0][1], origen[0], origen[1]) > tolerancia_m:
            return None
        if distancia_aprox_metros(coords[-1][0], coords[-1][1], destino[0], destino[1]) > tolerancia_m:
            return None

        # Además del extremo vial almacenado, valida el punto que el usuario
        # marcó originalmente. Así un cálculo viejo que se enganchó a una calle
        # demasiado lejana se considera dañado y se reconstruye para la vista.
        detalle = tramo.detalle_prediccion or {}
        plan_general = detalle.get("plan_general", {}) if isinstance(detalle, dict) else {}
        destino_original = plan_general.get("destino_original")
        if isinstance(destino_original, (list, tuple)) and len(destino_original) >= 2:
            try:
                if distancia_aprox_metros(
                    coords[-1][0], coords[-1][1],
                    float(destino_original[0]), float(destino_original[1]),
                ) > 95.0:
                    return None
            except (TypeError, ValueError, IndexError):
                pass
        if indice_tramo == 0:
            origen_original = plan_general.get("origen_original")
            if isinstance(origen_original, (list, tuple)) and len(origen_original) >= 2:
                try:
                    if distancia_aprox_metros(
                        coords[0][0], coords[0][1],
                        float(origen_original[0]), float(origen_original[1]),
                    ) > 95.0:
                        return None
                except (TypeError, ValueError, IndexError):
                    pass

        # Detecta saltos internos anómalos. Un tramo urbano normal puede tener
        # puntos separados, pero no debe teletransportarse cientos de metros.
        for a, b in zip(coords[:-1], coords[1:]):
            if distancia_aprox_metros(a[0], a[1], b[0], b[1]) > 350.0:
                return None

        if fin_anterior is not None:
            separacion = distancia_aprox_metros(
                fin_anterior[0], fin_anterior[1], coords[0][0], coords[0][1]
            )
            if separacion > tolerancia_m:
                return None
            # El mismo punto se reutiliza literalmente para que Google Maps no
            # muestre una grieta de uno o dos píxeles entre colores.
            coords[0] = list(fin_anterior)

        rutas.append(coords)
        fin_anterior = list(coords[-1])

    return rutas


def _puntos_originales_plan_general(tramos):
    """Recupera la secuencia que el administrador marcó originalmente."""
    if not tramos:
        return []

    def _par(valor, defecto):
        try:
            if isinstance(valor, (list, tuple)) and len(valor) >= 2:
                lat = float(valor[0])
                lon = float(valor[1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return [lat, lon]
        except (TypeError, ValueError, IndexError):
            pass
        return list(defecto)

    primero = tramos[0]
    detalle_primero = primero.detalle_prediccion or {}
    plan_primero = detalle_primero.get("plan_general", {}) if isinstance(detalle_primero, dict) else {}
    origen_defecto = [float(primero.origen_latitud), float(primero.origen_longitud)]
    puntos = [{
        "numero": int(primero.orden) - 1,
        "nombre": primero.origen_nombre,
        "coords": _par(plan_primero.get("origen_original"), origen_defecto),
    }]

    for tramo in tramos:
        detalle = tramo.detalle_prediccion or {}
        plan_general = detalle.get("plan_general", {}) if isinstance(detalle, dict) else {}
        destino_defecto = [float(tramo.destino_latitud), float(tramo.destino_longitud)]
        puntos.append({
            "numero": int(tramo.orden),
            "nombre": tramo.destino_nombre,
            "coords": _par(plan_general.get("destino_original"), destino_defecto),
        })
    return puntos


def _reconstruir_rutas_generales_visuales(tramos):
    """Reconstruye solo la geometría visual de planes antiguos dañados.

    Usa la misma red dirigida y Dijkstra, pero sin consultar APIs externas ni
    alterar distancias, consumos o costos guardados. El objetivo es reparar la
    visualización histórica cuando la geometría vieja quedó partida.
    """
    puntos = _puntos_originales_plan_general(tramos)
    if len(puntos) != len(tramos) + 1:
        return None

    grafo = construir_grafo_con_costos({})
    rutas = []
    continuidad = None
    fin_anterior = None

    for indice, tramo in enumerate(tramos):
        origen_original = puntos[indice]["coords"]
        destino_original = puntos[indice + 1]["coords"]

        if continuidad:
            enganche = _seleccionar_enganche_general_continuo(
                continuidad_origen=continuidad,
                lat_destino=destino_original[0],
                lon_destino=destino_original[1],
                grafo=grafo,
            )
        else:
            enganche = _seleccionar_enganche_general_inicial(
                lat_origen=origen_original[0],
                lon_origen=origen_original[1],
                lat_destino=destino_original[0],
                lon_destino=destino_original[1],
                grafo=grafo,
            )

        if not enganche:
            return None

        if enganche.get("ruta_directa"):
            ruta_ids = []
            distancia_base_km = float(enganche["tramo_directo"].distancia_km or 0) * float(
                enganche.get("fraccion_directa", 0.0)
            )
        else:
            ruta_ids, _ = dijkstra(
                grafo,
                enganche["nodo_origen"].id_nodo,
                enganche["nodo_destino"].id_nodo,
            )
            if not ruta_ids:
                return None
            distancia_base_km = metricas_avanzadas_ruta(ruta_ids)["distancia_km"]
            parciales = metricas_parciales_enganche(enganche)
            distancia_base_km += float(parciales.get("distancia_km", 0.0))

        coords = _construir_geometria_general_segura(ruta_ids, enganche)
        if not _geometria_general_valida(
            coords,
            enganche["origen"]["punto_ajustado"],
            enganche["destino"]["punto_ajustado"],
            distancia_base_km,
        ):
            return None

        if fin_anterior is not None:
            separacion = distancia_aprox_metros(
                fin_anterior[0], fin_anterior[1], coords[0][0], coords[0][1]
            )
            if separacion > 3.0:
                return None
            coords[0] = list(fin_anterior)

        rutas.append(coords)
        fin_anterior = list(coords[-1])
        continuidad = {
            "tramo_id": int(enganche["destino"]["tramo"].pk),
            "lat": float(enganche["destino"]["punto_ajustado"][0]),
            "lon": float(enganche["destino"]["punto_ajustado"][1]),
            "fraccion_proyeccion": float(
                enganche["destino"].get("fraccion_proyeccion", 0.0)
            ),
        }

    return rutas


def _puntos_visuales_desde_rutas(tramos, rutas):
    """Crea marcadores exactamente en los extremos de la geometría mostrada."""
    puntos = []
    if not tramos or not rutas:
        return puntos

    primera = rutas[0]
    if not primera:
        return puntos
    puntos.append({
        "numero": int(tramos[0].orden) - 1,
        "nombre": tramos[0].origen_nombre,
        "lat": float(primera[0][0]),
        "lon": float(primera[0][1]),
    })

    for tramo, coords in zip(tramos, rutas):
        if not coords:
            continue
        puntos.append({
            "numero": int(tramo.orden),
            "nombre": tramo.destino_nombre,
            "lat": float(coords[-1][0]),
            "lon": float(coords[-1][1]),
        })
    return puntos

def admin_detalle_tramos_generales(request, id_viaje):
    administrador = _administrador_actual(request)
    if not administrador:
        return redirect("login")
    try:
        viaje = (
            Viaje.objects
            .select_related("usuario", "vehiculo", "plan_carga", "administrador_ejecutor")
            .get(
                id_viaje=id_viaje,
                es_plan_general=True,
                administrador_ejecutor=administrador,
            )
        )
    except Viaje.DoesNotExist:
        messages.error(request, "El plan general solicitado no existe.")
        return redirect("admin_tramos_generales")

    tramos = list(
        viaje.tramos
        .select_related("ruta_seleccionada")
        .prefetch_related("entregas_realizadas")
        .order_by("orden")
    )
    # Primero se intenta usar exactamente la ruta recomendada que quedó
    # guardada. Si corresponde a un cálculo antiguo con geometría partida, se
    # reconstruye SOLO la línea visual sobre la misma red vial para evitar
    # fragmentos flotantes en el mapa. Los cálculos y métricas históricas no se
    # modifican.
    rutas_json = _rutas_generales_guardadas_continuas(tramos)
    ruta_visual_reparada = False
    if rutas_json is None and tramos:
        rutas_json = _reconstruir_rutas_generales_visuales(tramos)
        ruta_visual_reparada = rutas_json is not None
    if rutas_json is None:
        rutas_json = [_coords_general_limpias(tramo.geometria_ruta or []) for tramo in tramos]

    puntos = _puntos_visuales_desde_rutas(tramos, rutas_json)

    return render(request, "administrador/rutas/detalle_tramos_generales.html", {
        "viaje": viaje,
        "tramos": tramos,
        "rutas_json": json.dumps(rutas_json),
        "puntos_json": json.dumps(puntos),
        "ruta_visual_reparada": ruta_visual_reparada,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
    })


@require_GET
def admin_pdf_tramos_generales(request, id_viaje):
    administrador = _administrador_actual(request)
    if not administrador:
        return redirect("login")
    try:
        viaje = Viaje.objects.select_related(
            "usuario", "vehiculo", "plan_carga", "administrador_ejecutor"
        ).get(
            id_viaje=id_viaje,
            es_plan_general=True,
            administrador_ejecutor=administrador,
        )
    except Viaje.DoesNotExist:
        messages.error(request, "El plan general solicitado no existe.")
        return redirect("admin_tramos_generales")

    tramos = _tramos_para_pdf(viaje)
    rutas_pdf = _rutas_generales_guardadas_continuas(tramos)
    if rutas_pdf is None and tramos:
        rutas_pdf = _reconstruir_rutas_generales_visuales(tramos)
    if rutas_pdf:
        # Solo se sustituye en memoria para el dibujo del PDF; no se alteran
        # los registros históricos ni sus métricas.
        for tramo, coords in zip(tramos, rutas_pdf):
            tramo.geometria_ruta = coords

    unidad = _unidad_combustible_pdf(request)
    contenido = construir_pdf_viaje(viaje, tramos, unidad_combustible=unidad)
    _respaldar_pdf_seguro(viaje, contenido, unidad)
    respuesta = HttpResponse(contenido, content_type="application/pdf")
    sufijo_unidad = "galones" if unidad == "GALONES" else "litros"
    respuesta["Content-Disposition"] = (
        f'attachment; filename="tramos_generales_{viaje.id_viaje}_{sufijo_unidad}.pdf"'
    )
    return respuesta

def admin_planificacion_rutas(request):
    administrador = _administrador_actual(request)
    if not administrador:
        messages.error(request, "No tienes permisos para acceder a la planificación de rutas.")
        return redirect("login")

    planes_consulta = (
        PlanCarga.objects
        .filter(
            vehiculo__usuario__isnull=False,
            vehiculo__usuario__activo=True,
            vehiculo__usuario__tiporol="USUARIO",
            estado__in=["LISTO", "CONFIRMADO", "EN_RUTA", "COMPLETADO"],
        )
        .select_related("vehiculo", "vehiculo__usuario")
        .prefetch_related("detalles__producto")
        .order_by("vehiculo__usuario__apellido_usuario", "-fecha_planificada")
    )

    planes_disponibles = []
    usuarios_ids = set()
    vehiculos_ids = set()
    for plan in planes_consulta:
        peso = plan.peso_total_kg
        if peso <= 0:
            continue
        conductor = plan.vehiculo.usuario
        planes_disponibles.append({
            "plan": plan,
            "usuario": conductor,
            "vehiculo": plan.vehiculo,
            "peso": peso,
            "productos": plan.detalles.filter(cantidad_actual__gt=0).count(),
            "es_hoy": plan.fecha_planificada == timezone.localdate(),
        })
        usuarios_ids.add(conductor.id_usuario)
        vehiculos_ids.add(plan.vehiculo_id)

    usuarios = list(
        Usuario.objects.filter(id_usuario__in=usuarios_ids).order_by(
            "apellido_usuario", "nombre_usuario"
        )
    )
    vehiculos = list(
        Vehiculo.objects.filter(id_vehiculo__in=vehiculos_ids)
        .select_related("usuario")
        .order_by("matricula_vehiculo")
    )

    pruebas = (
        Viaje.objects
        .filter(es_prueba_administrativa=True, administrador_ejecutor=administrador)
        .select_related("usuario", "vehiculo", "plan_carga")
        .prefetch_related("tramos")
        .order_by("-fecha_creacion")[:8]
    )

    modo_activo = _modo_admin_rutas(request)
    seleccion = None
    if modo_activo:
        seleccion = {
            "usuario": _usuario_actual(request),
            "vehiculo": _vehiculo_usuario(_usuario_actual(request), request),
            "plan_id": request.session.get("ruta_admin_plan_id"),
        }

    return render(request, "administrador/rutas/planificacion_rutas.html", {
        "planes_disponibles": planes_disponibles,
        "usuarios": usuarios,
        "vehiculos": vehiculos,
        "pruebas": pruebas,
        "modo_activo": modo_activo,
        "seleccion": seleccion,
        "total_combinaciones": len(planes_disponibles),
        "total_conductores": len(usuarios),
        "total_vehiculos": len(vehiculos),
        "total_pruebas": Viaje.objects.filter(
            es_prueba_administrativa=True,
            administrador_ejecutor=administrador,
        ).count(),
    })


@require_POST
def admin_iniciar_prueba_rutas(request):
    administrador = _administrador_actual(request)
    if not administrador:
        messages.error(request, "No tienes permisos para iniciar pruebas de ruta.")
        return redirect("login")

    vehiculo_id = request.POST.get("vehiculo_id")
    plan_id = request.POST.get("plan_id")

    try:
        plan = (
            PlanCarga.objects
            .select_related("vehiculo", "vehiculo__usuario")
            .prefetch_related("detalles__producto")
            .get(
                id_plan_carga=plan_id,
                vehiculo_id=vehiculo_id,
                vehiculo__usuario__isnull=False,
                vehiculo__usuario__activo=True,
                vehiculo__usuario__tiporol="USUARIO",
                estado__in=["LISTO", "CONFIRMADO", "EN_RUTA", "COMPLETADO"],
            )
        )
    except (PlanCarga.DoesNotExist, TypeError, ValueError):
        messages.error(request, "La combinación de vehículo y carga no es válida.")
        return redirect("admin_planificacion_rutas")

    if plan.peso_total_kg <= 0:
        messages.error(request, "La carga seleccionada no tiene productos disponibles para la prueba.")
        return redirect("admin_planificacion_rutas")

    _limpiar_modo_admin_rutas(request)
    request.session["ruta_admin_modo"] = True
    request.session["ruta_admin_usuario_id"] = plan.vehiculo.usuario_id
    request.session["ruta_admin_vehiculo_id"] = plan.vehiculo_id
    request.session["ruta_admin_plan_id"] = plan.id_plan_carga
    request.session.modified = True

    messages.success(
        request,
        f"Prueba preparada para {plan.vehiculo.usuario.nombre_usuario} "
        f"{plan.vehiculo.usuario.apellido_usuario} con el vehículo "
        f"{plan.vehiculo.matricula_vehiculo}.",
    )
    return redirect("buscarlugares")


@require_POST
def admin_salir_prueba_rutas(request):
    administrador = _administrador_actual(request)
    if not administrador:
        return redirect("login")
    _limpiar_modo_admin_rutas(request)
    messages.info(request, "El modo de prueba administrativa fue cerrado.")
    return redirect("admin_planificacion_rutas")


def admin_reportes_viajes(request):
    administrador = _administrador_actual(request)
    if not administrador:
        messages.error(request, "No tienes permisos para consultar los reportes de viajes.")
        return redirect("login")

    fecha_texto = (request.GET.get("fecha") or "").strip()
    usuario_texto = (request.GET.get("usuario") or "").strip()
    vehiculo_texto = (request.GET.get("vehiculo") or "").strip()
    estado = (request.GET.get("estado") or "").strip().upper()
    tipo = (request.GET.get("tipo") or "").strip().upper()

    viajes = (
        Viaje.objects
        .select_related(
            "usuario",
            "vehiculo",
            "plan_carga",
            "administrador_ejecutor",
        )
        .prefetch_related(
            Prefetch(
                "tramos",
                queryset=TramoViaje.objects.order_by("orden").prefetch_related(
                    "entregas_realizadas"
                ),
            ),
            Prefetch(
                "respaldos_pdf",
                queryset=ReportePDFViaje.objects.order_by("-fecha_respaldo"),
                to_attr="respaldos_cloud",
            ),
        )
        .order_by("-fecha_creacion")
    )

    fecha = parse_date(fecha_texto) if fecha_texto else None
    if fecha:
        viajes = viajes.filter(fecha_creacion__date=fecha)
    if usuario_texto:
        viajes = viajes.filter(usuario_id=usuario_texto)
    if vehiculo_texto:
        viajes = viajes.filter(vehiculo_id=vehiculo_texto)
    if estado in {valor for valor, _ in Viaje.ESTADOS}:
        viajes = viajes.filter(estado=estado)
    if tipo == "PRUEBA":
        viajes = viajes.filter(es_prueba_administrativa=True, es_plan_general=False).filter(
            Q(administrador_ejecutor=administrador)
            | Q(administrador_ejecutor__isnull=True)
        )
    elif tipo == "GENERAL":
        viajes = viajes.filter(es_plan_general=True).filter(
            Q(administrador_ejecutor=administrador)
            | Q(administrador_ejecutor__isnull=True)
        )
    elif tipo == "OPERATIVO":
        viajes = viajes.filter(es_prueba_administrativa=False, es_plan_general=False)

    resumen = viajes.aggregate(
        distancia=Sum("distancia_estimada_total_km"),
        tiempo=Sum("tiempo_estimado_total_min"),
        combustible=Sum("consumo_estimado_total_l"),
        costo=Sum("costo_estimado_total"),
    )

    usuarios = Usuario.objects.filter(
        tiporol="USUARIO",
        viajes__isnull=False,
    ).distinct().order_by("apellido_usuario", "nombre_usuario")
    vehiculos = Vehiculo.objects.filter(viajes__isnull=False).distinct().order_by(
        "matricula_vehiculo"
    )

    return render(request, "administrador/rutas/reportes_viajes.html", {
        "viajes": viajes,
        "usuarios": usuarios,
        "vehiculos": vehiculos,
        "resumen": resumen,
        "filtros": {
            "fecha": fecha_texto,
            "usuario": usuario_texto,
            "vehiculo": vehiculo_texto,
            "estado": estado,
            "tipo": tipo,
        },
        "total_viajes": viajes.count(),
        "total_pruebas": viajes.filter(es_prueba_administrativa=True, es_plan_general=False).count(),
        "total_operativos": viajes.filter(es_prueba_administrativa=False, es_plan_general=False).count(),
        "total_generales": viajes.filter(es_plan_general=True).count(),
    })


def admin_detalle_viaje(request, id_viaje):
    administrador = _administrador_actual(request)
    if not administrador:
        return redirect("login")
    try:
        viaje = Viaje.objects.select_related(
            "usuario", "vehiculo", "plan_carga", "administrador_ejecutor"
        ).get(id_viaje=id_viaje)
    except Viaje.DoesNotExist:
        messages.error(request, "El viaje solicitado no existe.")
        return redirect("admin_reportes_viajes")

    if (
        viaje.es_prueba_administrativa
        and viaje.administrador_ejecutor_id is not None
        and viaje.administrador_ejecutor_id != administrador.id_usuario
    ):
        messages.error(request, "Esta prueba administrativa pertenece a otro administrador.")
        return redirect(f"{reverse('admin_reportes_viajes')}?tipo=PRUEBA")

    tramos = (
        viaje.tramos
        .select_related("ruta_seleccionada")
        .prefetch_related(
            "entregas_realizadas__detalle_carga__producto",
            "puntos_gps",
        )
        .order_by("orden")
    )
    return render(request, "administrador/rutas/detalle_viaje.html", {
        "viaje": viaje,
        "tramos": tramos,
    })


@require_GET
def admin_reporte_pdf_viaje(request, id_viaje):
    administrador = _administrador_actual(request)
    if not administrador:
        return redirect("login")
    try:
        viaje = Viaje.objects.select_related(
            "usuario", "vehiculo", "plan_carga", "administrador_ejecutor"
        ).get(id_viaje=id_viaje)
    except Viaje.DoesNotExist:
        messages.error(request, "El viaje solicitado no existe.")
        return redirect("admin_reportes_viajes")

    if (
        viaje.es_prueba_administrativa
        and viaje.administrador_ejecutor_id is not None
        and viaje.administrador_ejecutor_id != administrador.id_usuario
    ):
        messages.error(request, "Esta prueba administrativa pertenece a otro administrador.")
        return redirect(f"{reverse('admin_reportes_viajes')}?tipo=PRUEBA")

    tramos = _tramos_para_pdf(viaje)
    unidad = _unidad_combustible_pdf(request)
    contenido = construir_pdf_viaje(viaje, tramos, unidad_combustible=unidad)
    _respaldar_pdf_seguro(viaje, contenido, unidad)
    response = HttpResponse(contenido, content_type="application/pdf")
    etiqueta = "prueba" if viaje.es_prueba_administrativa else "viaje"
    sufijo = "galones" if unidad == "GALONES" else "litros"
    response["Content-Disposition"] = (
        f'attachment; filename="{etiqueta}_{viaje.id_viaje}_distric_c_{sufijo}.pdf"'
    )
    return response


@require_GET
def api_ruta_optima(request):
    usuario = _usuario_actual(request)
    if not usuario:
        return JsonResponse({"ok": False}, status=401)

    consulta = RutaOpcion.objects.filter(
        viaje__usuario=usuario,
        es_recomendada=True,
    )
    if _modo_admin_rutas(request):
        consulta = consulta.filter(
            viaje__es_prueba_administrativa=True,
            viaje__administrador_ejecutor=_administrador_actual(request),
        )
    else:
        consulta = consulta.filter(viaje__es_prueba_administrativa=False)

    opcion = consulta.order_by("-fecha_calculo").first()
    if not opcion:
        return JsonResponse({"ok": False, "mensaje": "No existe una ruta recomendada."}, status=404)

    return JsonResponse({
        "ok": True,
        "ruta_id": opcion.id_ruta_opcion,
        "distancia_km": opcion.distancia_km,
        "tiempo_min": opcion.tiempo_min,
        "consumo_litros": float(opcion.consumo_predicho_litros),
        "costo_estimado": opcion.costo_estimado,
        "modelo_ia": opcion.modelo_ia,
    })
