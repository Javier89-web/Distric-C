import json
import math
import time
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError
from Aplicaciones.proyectos.models import NodoMapa, TramoVial


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def clasificar_tipo_via(highway_value):
    if highway_value in ("motorway", "trunk", "primary"):
        return "PRINCIPAL"
    elif highway_value in ("secondary", "tertiary"):
        return "SECUNDARIA"
    elif highway_value in ("residential", "living_street", "service", "unclassified"):
        return "URBANA"
    else:
        return "RURAL"


def velocidad_por_tipo_via(tipo_via):
    if tipo_via == "PRINCIPAL":
        return 60.0
    elif tipo_via == "SECUNDARIA":
        return 50.0
    elif tipo_via == "URBANA":
        return 30.0
    else:
        return 40.0


class Command(BaseCommand):
    help = "Importa tramos viales (ways de OSM) desde el mismo JSON a la tabla TramoVial (optimizado para Render)"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)

    def handle(self, *args, **options):
        file_path = options["file_path"]
        self.stdout.write(self.style.NOTICE(f"Leyendo archivo: {file_path}"))

        # ✅ Confirmar DB (Render vs local)
        self.stdout.write(
            f"DB => HOST={connection.settings_dict.get('HOST')} "
            f"NAME={connection.settings_dict.get('NAME')}"
        )

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        elementos = data.get("elements", [])

        # ✅ OPTIMIZACIÓN: precargar coords de TODOS los nodos 1 sola vez
        # nodos_xy: {id_nodo: (lat, lon)}
        self.stdout.write("Precargando coordenadas de nodos...")
        nodos_xy = {
            n["id_nodo"]: (n["latitud"], n["longitud"])
            for n in NodoMapa.objects.values("id_nodo", "latitud", "longitud")
        }
        self.stdout.write(f"Coordenadas cargadas: {len(nodos_xy)} nodos")

        total_ways = 0
        total_tramos_intentados = 0
        total_tramos_insertados_aprox = 0

        BATCH_SIZE = 2000
        batch = []

        def insertar_lote(lote):
            nonlocal total_tramos_insertados_aprox
            for intento in range(1, 6):
                try:
                    TramoVial.objects.bulk_create(
                        lote,
                        ignore_conflicts=True,
                        batch_size=BATCH_SIZE
                    )
                    total_tramos_insertados_aprox += len(lote)
                    return
                except OperationalError as e:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Se cortó SSL (intento {intento}/5): {e}. Reintentando..."
                    ))
                    connection.close()
                    time.sleep(2 * intento)
            raise OperationalError("No se pudo insertar el lote tras varios reintentos.")

        for el in elementos:
            if el.get("type") != "way":
                continue

            tags = el.get("tags", {})
            if "highway" not in tags:
                continue

            highway_value = tags.get("highway")
            tipo_via = clasificar_tipo_via(highway_value)

            nodes_list = el.get("nodes", [])
            if len(nodes_list) < 2:
                continue

            total_ways += 1

            # pares consecutivos
            for idx in range(len(nodes_list) - 1):
                osm_id_origen = nodes_list[idx]
                osm_id_destino = nodes_list[idx + 1]

                # ✅ ya no consultamos BD: buscamos coordenadas en dict
                origen_xy = nodos_xy.get(osm_id_origen)
                destino_xy = nodos_xy.get(osm_id_destino)
                if not origen_xy or not destino_xy:
                    continue

                total_tramos_intentados += 1

                lat1, lon1 = origen_xy
                lat2, lon2 = destino_xy

                dist_km = haversine_km(lat1, lon1, lat2, lon2)

                vel_kmh = velocidad_por_tipo_via(tipo_via)
                tiempo_min = (dist_km / vel_kmh) * 60.0 if vel_kmh > 0 else 0.0

                # tramo ida
                batch.append(TramoVial(
                    origen_id=osm_id_origen,
                    destino_id=osm_id_destino,
                    distancia_km=dist_km,
                    tiempo_base_min=tiempo_min,
                    tipo_via=tipo_via,
                ))

                # tramo vuelta
                batch.append(TramoVial(
                    origen_id=osm_id_destino,
                    destino_id=osm_id_origen,
                    distancia_km=dist_km,
                    tiempo_base_min=tiempo_min,
                    tipo_via=tipo_via,
                ))

                if len(batch) >= BATCH_SIZE:
                    insertar_lote(batch)
                    self.stdout.write(f"Ways: {total_ways} | Tramos intentados: {total_tramos_intentados}")
                    batch.clear()

        if batch:
            insertar_lote(batch)

        self.stdout.write(self.style.SUCCESS("✅ Importación de tramos completada (por lotes)"))
        self.stdout.write(f"Total ways procesados: {total_ways}")
        self.stdout.write(f"Tramos intentados (pares de nodos): {total_tramos_intentados}")
        self.stdout.write(f"Tramos insertados (aprox, incluye ignorados si ya existían): {total_tramos_insertados_aprox}")
        self.stdout.write(f"Total tramos actualmente en la BD: {TramoVial.objects.count()}")
