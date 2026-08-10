import json
from pathlib import Path

import osmnx as ox


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

LUGAR = "Latacunga, Cotopaxi, Ecuador"

CARPETA_SALIDA = Path(__file__).resolve().parent

ARCHIVO_GRAPHML = CARPETA_SALIDA / "latacunga_drive.graphml"
ARCHIVO_JSON = CARPETA_SALIDA / "latacunga_osmnx.json"


# ==========================================================
# FUNCIONES
# ==========================================================

def limpiar_valor(valor):
    """
    OSMnx a veces devuelve listas, números o textos.
    Esta función deja todo en un formato seguro para JSON.
    """
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor)

    if valor is None:
        return ""

    return valor


def generar_red():
    print("Descargando red vial de Latacunga...")

    ox.settings.use_cache = True
    ox.settings.log_console = True

    # network_type='drive' descarga red para vehículos
    # OSMnx devuelve un grafo dirigido, importante para respetar sentidos.
    G = ox.graph_from_place(
        LUGAR,
        network_type="drive",
        simplify=True
    )

    print("Agregando velocidades y tiempos aproximados...")

    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    print("Guardando respaldo GraphML...")

    ox.save_graphml(G, ARCHIVO_GRAPHML)

    print("Convirtiendo a JSON compatible...")

    nodos = []
    tramos = []

    for node_id, data in G.nodes(data=True):
        nodos.append({
            "id": int(node_id),
            "latitud": float(data.get("y")),
            "longitud": float(data.get("x"))
        })

    for origen, destino, key, data in G.edges(keys=True, data=True):
        nombre = limpiar_valor(data.get("name"))
        highway = limpiar_valor(data.get("highway"))
        oneway = limpiar_valor(data.get("oneway"))

        distancia_m = float(data.get("length", 0))
        tiempo_seg = float(data.get("travel_time", 0))
        velocidad_kph = float(data.get("speed_kph", 0)) if data.get("speed_kph") else 0

        tramo = {
            "origen": int(origen),
            "destino": int(destino),

            "distancia_m": round(distancia_m, 2),
            "distancia_km": round(distancia_m / 1000, 4),

            "tiempo_seg": round(tiempo_seg, 2),
            "tiempo_min": round(tiempo_seg / 60, 2),

            "velocidad_kph": round(velocidad_kph, 2),

            "nombre": nombre,
            "tipo_via": highway,
            "oneway": oneway,

            "osm_key": int(key)
        }

        # Si tiene geometría, guardamos la línea real de la calle
        if "geometry" in data:
            tramo["geometry"] = [
                [round(lat, 7), round(lon, 7)]
                for lon, lat in data["geometry"].coords
            ]
        else:
            tramo["geometry"] = []

        tramos.append(tramo)

    salida = {
        "fuente": "OSMnx + OpenStreetMap",
        "lugar": LUGAR,
        "tipo_red": "drive",
        "descripcion": "Red vial dirigida para rutas vehiculares en Latacunga.",
        "total_nodos": len(nodos),
        "total_tramos": len(tramos),
        "nodos": nodos,
        "tramos": tramos
    }

    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print("Proceso terminado.")
    print(f"Nodos generados: {len(nodos)}")
    print(f"Tramos generados: {len(tramos)}")
    print(f"Archivo JSON: {ARCHIVO_JSON}")
    print(f"Archivo GraphML: {ARCHIVO_GRAPHML}")


# ==========================================================
# EJECUCIÓN
# ==========================================================

if __name__ == "__main__":
    generar_red()