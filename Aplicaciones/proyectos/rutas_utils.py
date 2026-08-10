"""Utilidades para la red vial, Dijkstra y geometrías de rutas.

Las rutas se calculan sobre la red dirigida importada desde OSMnx. Además de
buscar caminos de mínimo costo, este módulo ajusta el origen y el destino a la
calzada más cercana y recorta los primeros/últimos tramos. De esta manera la
línea dibujada sigue la geometría real de la vía y no crea un segmento recto a
través de terrenos o edificaciones.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
import math

from django.db.models import ExpressionWrapper, F, FloatField

from Aplicaciones.proyectos.models import NodoMapa, TramoVial


# ----------------- CACHÉ DE TRAMOS -----------------

_tramos_cache = None
_tramos_index_cache = None
_geometrias_cache = None


def obtener_tramos():
    """Devuelve todos los ``TramoVial`` en memoria."""
    global _tramos_cache, _tramos_index_cache, _geometrias_cache

    if _tramos_cache is None:
        _tramos_cache = list(
            TramoVial.objects.select_related("origen", "destino").all()
        )
        _tramos_index_cache = None
        _geometrias_cache = None

    return _tramos_cache


def obtener_index_tramos():
    """Devuelve ``(origen_id, destino_id) -> TramoVial``.

    Si la base contiene aristas paralelas entre los mismos nodos se conserva
    una sola: primero la de menor tiempo y, en caso de empate, la de menor
    distancia. El cálculo, las métricas y la geometría usan así la misma arista.
    """
    global _tramos_index_cache

    if _tramos_index_cache is None:
        index = {}
        for tramo in obtener_tramos():
            clave = (int(tramo.origen_id), int(tramo.destino_id))
            actual = index.get(clave)
            tiempo = float(tramo.tiempo_base_min or float("inf"))
            distancia = float(tramo.distancia_km or float("inf"))
            if actual is None:
                index[clave] = tramo
                continue
            actual_tiempo = float(actual.tiempo_base_min or float("inf"))
            actual_distancia = float(actual.distancia_km or float("inf"))
            if (tiempo, distancia, tramo.pk) < (
                actual_tiempo,
                actual_distancia,
                actual.pk,
            ):
                index[clave] = tramo
        _tramos_index_cache = index

    return _tramos_index_cache


def limpiar_cache_tramos():
    """Vacía las cachés después de importar o modificar la red vial."""
    global _tramos_cache, _tramos_index_cache, _geometrias_cache
    _tramos_cache = None
    _tramos_index_cache = None
    _geometrias_cache = None


# ----------------- DISTANCIAS Y GEOMETRÍA -----------------


def distancia_aprox_metros(lat1, lon1, lat2, lon2):
    """Distancia haversine entre dos coordenadas, en metros."""
    radio_tierra = 6371000.0
    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(1 - a, 0)))
    return radio_tierra * c


def _coord_valida(punto):
    try:
        lat = float(punto[0])
        lon = float(punto[1])
    except (TypeError, ValueError, IndexError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return [lat, lon]


def _agregar_sin_repetir(destino, puntos):
    for punto in puntos or []:
        coord = _coord_valida(punto)
        if coord is None:
            continue
        if not destino or distancia_aprox_metros(
            destino[-1][0], destino[-1][1], coord[0], coord[1]
        ) > 0.35:
            destino.append(coord)
    return destino


def normalizar_geometria_tramo(tramo):
    """Obtiene la geometría orientada de ``origen`` hacia ``destino``.

    OSM puede almacenar la línea en el sentido contrario al de la arista. Se
    compara cada extremo con los nodos y se invierte cuando corresponde. Los
    nodos se fijan como extremos para que dos tramos consecutivos se unan sin
    saltos visuales.
    """
    global _geometrias_cache
    if _geometrias_cache is None:
        _geometrias_cache = {}

    clave = int(tramo.pk)
    if clave in _geometrias_cache:
        return [list(p) for p in _geometrias_cache[clave]]

    origen = [float(tramo.origen.latitud), float(tramo.origen.longitud)]
    destino = [float(tramo.destino.latitud), float(tramo.destino.longitud)]
    coords = []
    _agregar_sin_repetir(coords, tramo.geometria or [])

    if len(coords) < 2:
        coords = [origen, destino]
    else:
        costo_directo = (
            distancia_aprox_metros(coords[0][0], coords[0][1], origen[0], origen[1])
            + distancia_aprox_metros(coords[-1][0], coords[-1][1], destino[0], destino[1])
        )
        costo_inverso = (
            distancia_aprox_metros(coords[0][0], coords[0][1], destino[0], destino[1])
            + distancia_aprox_metros(coords[-1][0], coords[-1][1], origen[0], origen[1])
        )
        if costo_inverso + 0.5 < costo_directo:
            coords.reverse()

        if distancia_aprox_metros(origen[0], origen[1], coords[0][0], coords[0][1]) > 0.8:
            coords.insert(0, origen)
        else:
            coords[0] = origen

        if distancia_aprox_metros(destino[0], destino[1], coords[-1][0], coords[-1][1]) > 0.8:
            coords.append(destino)
        else:
            coords[-1] = destino

    depuradas = []
    _agregar_sin_repetir(depuradas, coords)
    if len(depuradas) < 2:
        depuradas = [origen, destino]

    _geometrias_cache[clave] = tuple(tuple(p) for p in depuradas)
    return [list(p) for p in depuradas]


def _xy_local(lat, lon, lat_ref):
    """Proyección local suficiente para medir segmentos urbanos."""
    y = float(lat) * 110574.0
    x = float(lon) * 111320.0 * math.cos(math.radians(float(lat_ref)))
    return x, y


def proyectar_punto_en_geometria(lat, lon, coords):
    """Proyecta un punto sobre una polilínea.

    Devuelve la coordenada proyectada, distancia a la vía, índice del segmento
    y fracción acumulada (0 inicio, 1 final).
    """
    coords = [_coord_valida(p) for p in (coords or [])]
    coords = [p for p in coords if p is not None]
    if len(coords) < 2:
        return None

    lat_ref = float(lat)
    px, py = _xy_local(lat, lon, lat_ref)
    longitudes = []
    total = 0.0
    for a, b in zip(coords[:-1], coords[1:]):
        longitud = distancia_aprox_metros(a[0], a[1], b[0], b[1])
        longitudes.append(longitud)
        total += longitud

    mejor = None
    acumulada = 0.0
    for indice, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
        ax, ay = _xy_local(a[0], a[1], lat_ref)
        bx, by = _xy_local(b[0], b[1], lat_ref)
        dx = bx - ax
        dy = by - ay
        denominador = dx * dx + dy * dy
        t = 0.0 if denominador <= 1e-12 else ((px - ax) * dx + (py - ay) * dy) / denominador
        t = max(0.0, min(1.0, t))
        qx = ax + t * dx
        qy = ay + t * dy
        distancia = math.hypot(px - qx, py - qy)
        lat_q = a[0] + t * (b[0] - a[0])
        lon_q = a[1] + t * (b[1] - a[1])
        recorrido = acumulada + longitudes[indice] * t
        fraccion = recorrido / total if total > 0 else 0.0
        candidato = {
            "punto": [lat_q, lon_q],
            "distancia_m": distancia,
            "indice_segmento": indice,
            "t_segmento": t,
            "fraccion": max(0.0, min(1.0, fraccion)),
            "longitud_total_m": total,
        }
        if mejor is None or candidato["distancia_m"] < mejor["distancia_m"]:
            mejor = candidato
        acumulada += longitudes[indice]
    return mejor


def _recortar_geometria(coords, proyeccion, desde_proyeccion):
    indice = int(proyeccion["indice_segmento"])
    punto = list(proyeccion["punto"])
    if desde_proyeccion:
        salida = [punto]
        _agregar_sin_repetir(salida, coords[indice + 1 :])
    else:
        salida = []
        _agregar_sin_repetir(salida, coords[: indice + 1])
        _agregar_sin_repetir(salida, [punto])
    return salida


def _recortar_entre_proyecciones(coords, inicio, fin):
    if inicio["fraccion"] > fin["fraccion"]:
        return []
    salida = [list(inicio["punto"])]
    ini = int(inicio["indice_segmento"])
    fin_i = int(fin["indice_segmento"])
    if ini == fin_i:
        _agregar_sin_repetir(salida, [fin["punto"]])
        return salida
    _agregar_sin_repetir(salida, coords[ini + 1 : fin_i + 1])
    _agregar_sin_repetir(salida, [fin["punto"]])
    return salida


def candidatos_enganche_vial(lat, lon, tipo="ORIGEN", k=14, radio_max_m=450.0):
    """Busca aristas vehiculares próximas y proyecta el punto sobre ellas."""
    tipo = str(tipo).upper()
    lat = float(lat)
    lon = float(lon)
    delta_lat = radio_max_m / 110574.0
    cos_lat = max(abs(math.cos(math.radians(lat))), 0.2)
    delta_lon = radio_max_m / (111320.0 * cos_lat)
    candidatos = []

    for tramo in obtener_index_tramos().values():
        origen_lat = float(tramo.origen.latitud)
        origen_lon = float(tramo.origen.longitud)
        destino_lat = float(tramo.destino.latitud)
        destino_lon = float(tramo.destino.longitud)
        if (
            max(origen_lat, destino_lat) < lat - delta_lat
            or min(origen_lat, destino_lat) > lat + delta_lat
            or max(origen_lon, destino_lon) < lon - delta_lon
            or min(origen_lon, destino_lon) > lon + delta_lon
        ):
            # Las geometrías curvas podrían salir ligeramente del bbox de nodos;
            # el margen de 450 m conserva suficientes candidatos urbanos.
            continue

        coords = normalizar_geometria_tramo(tramo)
        proyeccion = proyectar_punto_en_geometria(lat, lon, coords)
        if not proyeccion or proyeccion["distancia_m"] > radio_max_m:
            continue

        if tipo == "ORIGEN":
            nodo_red = int(tramo.destino_id)
            nodo_obj = tramo.destino
            fraccion_tramo = max(0.0, 1.0 - proyeccion["fraccion"])
            geometria_parcial = _recortar_geometria(coords, proyeccion, True)
        else:
            nodo_red = int(tramo.origen_id)
            nodo_obj = tramo.origen
            fraccion_tramo = max(0.0, proyeccion["fraccion"])
            geometria_parcial = _recortar_geometria(coords, proyeccion, False)

        candidatos.append({
            "tramo": tramo,
            "nodo_red": nodo_red,
            "nodo_obj": nodo_obj,
            "punto_ajustado": list(proyeccion["punto"]),
            "distancia_ajuste_m": float(proyeccion["distancia_m"]),
            "fraccion_proyeccion": float(proyeccion["fraccion"]),
            "fraccion_tramo": float(fraccion_tramo),
            "geometria_parcial": geometria_parcial,
            "proyeccion": proyeccion,
            "geometria_completa": coords,
        })

    candidatos.sort(
        key=lambda item: (
            item["distancia_ajuste_m"],
            float(item["tramo"].tiempo_base_min or 0),
            int(item["tramo"].pk),
        )
    )
    return candidatos[: max(1, min(int(k), 18))]


# ----------------- GRAFO + DIJKSTRA -----------------


def construir_grafo():
    """Grafo dirigido con ``tiempo_base_min`` como peso."""
    grafo = defaultdict(list)
    for tramo in obtener_index_tramos().values():
        costo = float(tramo.tiempo_base_min or 0)
        if costo > 0:
            grafo[int(tramo.origen_id)].append((int(tramo.destino_id), costo))
    return grafo


def dijkstra(grafo, origen_id, destino_id):
    return dijkstra_restringido(grafo, origen_id, destino_id)


def dijkstra_restringido(
    grafo,
    origen_id,
    destino_id,
    nodos_bloqueados=None,
    aristas_bloqueadas=None,
):
    """Dijkstra con exclusiones, utilizado también por Yen."""
    origen_id = int(origen_id)
    destino_id = int(destino_id)
    nodos_bloqueados = {int(n) for n in (nodos_bloqueados or set())}
    aristas_bloqueadas = {
        (int(u), int(v)) for u, v in (aristas_bloqueadas or set())
    }
    nodos_bloqueados.discard(origen_id)
    nodos_bloqueados.discard(destino_id)

    dist = {origen_id: 0.0}
    prev = {}
    heap = [(0.0, origen_id)]
    while heap:
        costo_actual, nodo = heapq.heappop(heap)
        if costo_actual > dist.get(nodo, float("inf")):
            continue
        if nodo == destino_id:
            break
        if nodo in nodos_bloqueados:
            continue
        for vecino, peso in grafo.get(nodo, []):
            vecino = int(vecino)
            if vecino in nodos_bloqueados or (nodo, vecino) in aristas_bloqueadas:
                continue
            peso = float(peso)
            if peso <= 0:
                continue
            nuevo_costo = costo_actual + peso
            if nuevo_costo < dist.get(vecino, float("inf")):
                dist[vecino] = nuevo_costo
                prev[vecino] = nodo
                heapq.heappush(heap, (nuevo_costo, vecino))

    if destino_id not in dist:
        return None, float("inf")

    ruta = [destino_id]
    while ruta[-1] != origen_id:
        anterior = prev.get(ruta[-1])
        if anterior is None:
            return None, float("inf")
        ruta.append(anterior)
    ruta.reverse()
    return ruta, dist[destino_id]


def _adyacencias_minimas(grafo):
    resultado = {}
    for origen, vecinos in grafo.items():
        for destino, peso in vecinos:
            clave = (int(origen), int(destino))
            peso = float(peso)
            if clave not in resultado or peso < resultado[clave]:
                resultado[clave] = peso
    return resultado


def costo_ruta(grafo, ruta):
    if not ruta or len(ruta) == 1:
        return 0.0
    pesos = _adyacencias_minimas(grafo)
    total = 0.0
    for u, v in zip(ruta[:-1], ruta[1:]):
        peso = pesos.get((int(u), int(v)))
        if peso is None:
            return float("inf")
        total += peso
    return total


def calcular_metricas_ruta(lista_ids_nodo):
    index_tramos = obtener_index_tramos()
    distancia_total = 0.0
    tiempo_total = 0.0
    for u, v in zip(lista_ids_nodo[:-1], lista_ids_nodo[1:]):
        tramo = index_tramos.get((int(u), int(v)))
        if tramo:
            distancia_total += float(tramo.distancia_km or 0)
            tiempo_total += float(tramo.tiempo_base_min or 0)
    return distancia_total, tiempo_total


# ------------- NODOS CERCANOS -------------


def nodos_mas_cercanos(lat, lon, k=5):
    dist_expr = ExpressionWrapper(
        (F("latitud") - lat) * (F("latitud") - lat)
        + (F("longitud") - lon) * (F("longitud") - lon),
        output_field=FloatField(),
    )
    return list(NodoMapa.objects.annotate(dist2=dist_expr).order_by("dist2")[:k])


def nodo_mas_cercano(lat, lon):
    resultados = nodos_mas_cercanos(lat, lon, k=1)
    return resultados[0] if resultados else None


def penalizacion_enganche_min(distancia_metros):
    # Aproxima una velocidad lenta de acceso de 25 m/min. La distancia no se
    # dibuja como recta: solo evita escoger una calzada lejana.
    return float(distancia_metros) / 25.0


def _peso_arista_grafo(grafo, origen, destino, defecto=0.0):
    pesos = [
        float(peso)
        for vecino, peso in grafo.get(int(origen), [])
        if int(vecino) == int(destino)
    ]
    return min(pesos) if pesos else float(defecto)


def seleccionar_mejor_enganche_ruta(
    lat_origen,
    lon_origen,
    lat_destino,
    lon_destino,
    grafo=None,
    k=14,
):
    """Ajusta origen/destino a aristas, no únicamente a nodos.

    El origen entra a la red desde el punto proyectado y continúa en el sentido
    de la vía. El destino sale de la red hasta su punto proyectado. Esto evita
    retrocesos artificiales y líneas rectas que atraviesan terrenos.
    """
    if grafo is None:
        grafo = construir_grafo()

    limite = max(6, min(int(k), 14))
    origenes = candidatos_enganche_vial(
        lat_origen, lon_origen, "ORIGEN", k=limite
    )
    destinos = candidatos_enganche_vial(
        lat_destino, lon_destino, "DESTINO", k=limite
    )
    if not origenes or not destinos:
        return None

    mejor = None

    # Caso directo: ambos puntos se encuentran sobre la misma arista y en el
    # orden permitido por su sentido vehicular.
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

    for origen in origenes:
        for destino in destinos:
            ruta_tmp, costo_tmp = dijkstra(
                grafo, origen["nodo_red"], destino["nodo_red"]
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


# ----------------- K MEJORES RUTAS -----------------


def rutas_muy_similares(r1_ids, r2_ids, umbral=0.9):
    if not r1_ids or not r2_ids:
        return False
    e1 = set(zip(r1_ids[:-1], r1_ids[1:]))
    e2 = set(zip(r2_ids[:-1], r2_ids[1:]))
    if not e1 or not e2:
        return True
    interseccion = len(e1 & e2)
    similitud = max(interseccion / len(e1), interseccion / len(e2))
    return similitud >= umbral


def _ruta_sin_repeticiones(ruta):
    return bool(ruta) and len(ruta) == len(set(ruta))


def k_mejores_rutas(
    grafo,
    origen_id,
    destino_id,
    k=6,
    penalizacion_base=1.55,
    umbral_similitud=0.78,
):
    """Genera rutas alternativas sin ciclos mediante Yen + Dijkstra.

    Yen usa Dijkstra repetidamente para producir caminos simples. Frente a la
    penalización acumulativa anterior, evita vueltas artificiales y retornos
    sobre la misma intersección. ``penalizacion_base`` se conserva en la firma
    por compatibilidad, pero ahora determina únicamente el límite razonable de
    desvío respecto a la mejor alternativa.
    """
    origen_id = int(origen_id)
    destino_id = int(destino_id)
    primera, primer_costo = dijkstra(grafo, origen_id, destino_id)
    if not primera:
        return []
    if origen_id == destino_id:
        return [(primera, 0.0)]

    aceptadas = [(primera, primer_costo)]
    firmas_aceptadas = {tuple(primera)}
    candidatas_heap = []
    firmas_candidatas = set()
    max_factor = max(1.85, min(float(penalizacion_base) + 0.65, 2.45))

    for _ in range(1, max(int(k), 1)):
        ruta_previa = aceptadas[-1][0]
        for indice in range(len(ruta_previa) - 1):
            nodo_desvio = ruta_previa[indice]
            raiz = ruta_previa[: indice + 1]
            aristas_bloqueadas = set()
            for ruta_existente, _ in aceptadas:
                if len(ruta_existente) > indice and ruta_existente[: indice + 1] == raiz:
                    aristas_bloqueadas.add(
                        (ruta_existente[indice], ruta_existente[indice + 1])
                    )
            nodos_bloqueados = set(raiz[:-1])
            desvio, _ = dijkstra_restringido(
                grafo,
                nodo_desvio,
                destino_id,
                nodos_bloqueados=nodos_bloqueados,
                aristas_bloqueadas=aristas_bloqueadas,
            )
            if not desvio:
                continue
            total = raiz[:-1] + desvio
            firma = tuple(total)
            if (
                firma in firmas_aceptadas
                or firma in firmas_candidatas
                or not _ruta_sin_repeticiones(total)
            ):
                continue
            costo = costo_ruta(grafo, total)
            if not math.isfinite(costo) or costo > primer_costo * max_factor:
                continue
            heapq.heappush(candidatas_heap, (costo, firma, total))
            firmas_candidatas.add(firma)

        siguiente = None
        while candidatas_heap:
            costo, firma, ruta = heapq.heappop(candidatas_heap)
            firmas_candidatas.discard(firma)
            if firma in firmas_aceptadas:
                continue
            # Rechaza copias casi idénticas, pero permite los tramos urbanos que
            # necesariamente comparten salida o llegada.
            if any(
                rutas_muy_similares(ruta, existente, umbral=umbral_similitud)
                for existente, _ in aceptadas
            ):
                continue
            siguiente = (ruta, costo)
            break
        if siguiente is None:
            break
        aceptadas.append(siguiente)
        firmas_aceptadas.add(tuple(siguiente[0]))

    aceptadas.sort(key=lambda item: item[1])
    return aceptadas[: max(1, int(k))]


def construir_grafo_con_costos(costos_por_arista):
    """Construye el grafo dinámico que recibe Dijkstra."""
    grafo = defaultdict(list)
    for tramo in obtener_index_tramos().values():
        clave = (int(tramo.origen_id), int(tramo.destino_id))
        costo = costos_por_arista.get(clave, tramo.tiempo_base_min)
        try:
            costo = float(costo)
        except (TypeError, ValueError):
            continue
        if costo > 0:
            grafo[clave[0]].append((clave[1], costo))
    return grafo


def metricas_avanzadas_ruta(lista_ids_nodo):
    index_tramos = obtener_index_tramos()
    tipos = defaultdict(int)
    distancia_total = 0.0
    tiempo_total = 0.0
    detenciones = 0
    for u, v in zip(lista_ids_nodo[:-1], lista_ids_nodo[1:]):
        tramo = index_tramos.get((int(u), int(v)))
        if not tramo:
            continue
        distancia_total += float(tramo.distancia_km or 0)
        tiempo_total += float(tramo.tiempo_base_min or 0)
        tipo = tramo.tipo_via or "URBANA"
        tipos[tipo] += 1
        detenciones += 1 if tipo in {"PRINCIPAL", "RURAL"} else 2
    velocidad = (distancia_total / tiempo_total * 60.0) if tiempo_total > 0 else 0.0
    tipo_dominante = max(tipos, key=tipos.get) if tipos else "URBANA"
    return {
        "distancia_km": distancia_total,
        "tiempo_min": tiempo_total,
        "velocidad_promedio_kmh": velocidad,
        "detenciones_estimadas": detenciones,
        "tipo_via_dominante": tipo_dominante,
        "distribucion_vias": dict(tipos),
    }


def construir_coords_ruta_visual(ruta_ids):
    """Une las geometrías OSM de una ruta con orientación consistente."""
    if not ruta_ids or len(ruta_ids) < 2:
        return []
    index = obtener_index_tramos()
    coords = []
    for origen_id, destino_id in zip(ruta_ids[:-1], ruta_ids[1:]):
        tramo = index.get((int(origen_id), int(destino_id)))
        if tramo:
            geometria = normalizar_geometria_tramo(tramo)
        else:
            nodos = NodoMapa.objects.in_bulk(
                [int(origen_id), int(destino_id)], field_name="id_nodo"
            )
            origen = nodos.get(int(origen_id))
            destino = nodos.get(int(destino_id))
            geometria = []
            if origen:
                geometria.append([float(origen.latitud), float(origen.longitud)])
            if destino:
                geometria.append([float(destino.latitud), float(destino.longitud)])
        _agregar_sin_repetir(coords, geometria)
    return coords


def construir_geometria_ruta_ajustada(ruta_ids, enganche):
    """Crea la línea final recortada desde la vía del origen hasta la del destino."""
    if enganche.get("ruta_directa"):
        return [list(p) for p in enganche.get("ruta_directa_coords", [])]

    coords = []
    _agregar_sin_repetir(coords, enganche["origen"].get("geometria_parcial", []))
    _agregar_sin_repetir(coords, construir_coords_ruta_visual(ruta_ids))
    _agregar_sin_repetir(coords, enganche["destino"].get("geometria_parcial", []))
    return coords


def metricas_parciales_enganche(enganche):
    """Métricas de los fragmentos de arista recortados en los extremos."""
    if enganche.get("ruta_directa"):
        tramo = enganche["tramo_directo"]
        fraccion = float(enganche.get("fraccion_directa", 0))
        return {
            "distancia_km": float(tramo.distancia_km or 0) * fraccion,
            "tiempo_min": float(tramo.tiempo_base_min or 0) * fraccion,
            "tramos": [(tramo, fraccion)],
        }

    tramos = []
    distancia = 0.0
    tiempo = 0.0
    for extremo in ("origen", "destino"):
        dato = enganche[extremo]
        tramo = dato["tramo"]
        fraccion = float(dato.get("fraccion_tramo", 0))
        if fraccion <= 1e-8:
            continue
        tramos.append((tramo, fraccion))
        distancia += float(tramo.distancia_km or 0) * fraccion
        tiempo += float(tramo.tiempo_base_min or 0) * fraccion
    return {"distancia_km": distancia, "tiempo_min": tiempo, "tramos": tramos}
