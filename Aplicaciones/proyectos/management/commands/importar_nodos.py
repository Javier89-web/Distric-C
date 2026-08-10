import json
import time
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError
from Aplicaciones.proyectos.models import NodoMapa


class Command(BaseCommand):
    help = "Importa nodos OSM desde un archivo JSON (Overpass) a la tabla NodoMapa"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="Ruta al archivo JSON exportado de Overpass (por ejemplo red_vial_latacunga.json)",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]

        self.stdout.write(self.style.NOTICE(f"Leyendo archivo: {file_path}"))

        # ✅ Para confirmar que estás apuntando a Render y no a local
        self.stdout.write(
            f"DB => HOST={connection.settings_dict.get('HOST')} "
            f"NAME={connection.settings_dict.get('NAME')} "
            f"USER={connection.settings_dict.get('USER')}"
        )

        # 1) Cargar JSON
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        elementos = data.get("elements", [])

        total_nodos = 0
        creados_aprox = 0   # "aprox" porque con ignore_conflicts no sabemos exacto sin consultar
        existentes_aprox = 0

        BATCH_SIZE = 1000  # para Render (remoto) 500-2000 es ideal
        batch = []

        def insertar_lote(lote):
            """
            Inserta un lote con reintentos por si Render cierra SSL.
            """
            nonlocal creados_aprox

            for intento in range(1, 6):
                try:
                    # ignore_conflicts=True: si id_nodo (PK) ya existe, lo ignora (no duplica)
                    NodoMapa.objects.bulk_create(
                        lote,
                        ignore_conflicts=True,
                        batch_size=BATCH_SIZE
                    )
                    creados_aprox += len(lote)
                    return
                except OperationalError as e:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Se cortó la conexión SSL (intento {intento}/5). Reintentando..."
                    ))
                    # Cierra y espera un poco antes de reintentar
                    connection.close()
                    time.sleep(2 * intento)

            # si llega aquí, falló 5 veces
            raise OperationalError("No se pudo insertar el lote tras varios reintentos.")

        # 2) Preparar e insertar en lotes
        for el in elementos:
            if el.get("type") != "node":
                continue

            total_nodos += 1

            osm_id = el["id"]
            lat = el["lat"]
            lon = el["lon"]

            tags = el.get("tags", {})
            nombre = tags.get("name", f"Nodo {osm_id}")

            tipo = "INTERSECCION"

            batch.append(
                NodoMapa(
                    id_nodo=osm_id,
                    nombre=nombre,
                    latitud=lat,
                    longitud=lon,
                    tipo=tipo,
                )
            )

            if len(batch) >= BATCH_SIZE:
                insertar_lote(batch)
                self.stdout.write(f"Procesados: {total_nodos}")
                batch.clear()

        # último lote
        if batch:
            insertar_lote(batch)

        # 3) Resumen final (conteo exacto lo sacas con .count() si quieres)
        self.stdout.write(self.style.SUCCESS("✅ Importación de nodos completada (por lotes)"))
        self.stdout.write(f"Total nodos leídos en JSON: {total_nodos}")
        self.stdout.write(f"Nodos insertados (aprox, incluye ignorados si ya existían): {creados_aprox}")

        # ✅ Conteo exacto en BD (opcional pero útil)
        total_en_bd = NodoMapa.objects.count()
        self.stdout.write(f"Total de nodos actualmente en la BD: {total_en_bd}")
