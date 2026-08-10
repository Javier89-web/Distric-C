import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from Aplicaciones.proyectos.models import NodoMapa, TramoVial


class Command(BaseCommand):
    help = "Importa una red vial generada con OSMnx a NodoMapa y TramoVial."

    def add_arguments(self, parser):
        parser.add_argument(
            "archivo_json",
            type=str,
            help="Ruta del archivo JSON generado con OSMnx."
        )

        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Borra NodoMapa y TramoVial antes de importar la nueva red."
        )

    def cortar_texto(self, modelo, campo, texto):
        texto = str(texto or "").strip()

        try:
            max_length = modelo._meta.get_field(campo).max_length
            if max_length:
                return texto[:max_length]
        except Exception:
            pass

        return texto

    def mapear_tipo_via(self, tipo_osm):
        tipo = str(tipo_osm or "").lower()

        if "motorway" in tipo or "trunk" in tipo or "primary" in tipo:
            return "PRINCIPAL"

        if "secondary" in tipo or "tertiary" in tipo:
            return "SECUNDARIA"

        if "residential" in tipo or "living_street" in tipo or "service" in tipo:
            return "URBANA"

        if "unclassified" in tipo:
            return "URBANA"

        return "URBANA"

    def handle(self, *args, **options):
        archivo_json = Path(options["archivo_json"])

        if not archivo_json.exists():
            self.stdout.write(
                self.style.ERROR(f"No existe el archivo: {archivo_json}")
            )
            return

        self.stdout.write("Leyendo archivo OSMnx...")

        with open(archivo_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodos_json = data.get("nodos", [])
        tramos_json = data.get("tramos", [])

        self.stdout.write(f"Nodos encontrados en JSON: {len(nodos_json)}")
        self.stdout.write(f"Tramos encontrados en JSON: {len(tramos_json)}")

        with transaction.atomic():

            if options["limpiar"]:
                self.stdout.write("Limpiando red vial anterior...")
                TramoVial.objects.all().delete()
                NodoMapa.objects.all().delete()
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "No usaste --limpiar. Se intentará agregar la red encima de la actual."
                    )
                )

            self.stdout.write("Importando nodos...")

            nodos_creados = 0
            nodos_actualizados = 0

            for n in nodos_json:
                id_nodo = int(n["id"])

                nodo, creado = NodoMapa.objects.update_or_create(
                    id_nodo=id_nodo,
                    defaults={
                        "nombre": self.cortar_texto(
                            NodoMapa,
                            "nombre",
                            f"Nodo OSM {id_nodo}"
                        ),
                        "latitud": float(n["latitud"]),
                        "longitud": float(n["longitud"]),
                        "tipo": self.cortar_texto(NodoMapa, "tipo", "OSM"),
                    }
                )

                if creado:
                    nodos_creados += 1
                else:
                    nodos_actualizados += 1

            self.stdout.write("Cargando nodos en memoria...")

            nodos = {
                nodo.id_nodo: nodo
                for nodo in NodoMapa.objects.all()
            }

            self.stdout.write("Importando tramos dirigidos con geometría real...")

            tramos_para_crear = []
            tramos_omitidos = 0

            for t in tramos_json:
                origen_id = int(t["origen"])
                destino_id = int(t["destino"])

                origen = nodos.get(origen_id)
                destino = nodos.get(destino_id)

                if not origen or not destino:
                    tramos_omitidos += 1
                    continue

                distancia_km = float(t.get("distancia_km") or 0)
                tiempo_base_min = float(t.get("tiempo_min") or 0)

                if distancia_km <= 0:
                    tramos_omitidos += 1
                    continue

                if tiempo_base_min <= 0:
                    tiempo_base_min = max((distancia_km / 40) * 60, 0.1)

                tipo_via = self.mapear_tipo_via(t.get("tipo_via"))

                geometria = t.get("geometry") or []

                if not geometria:
                    geometria = [
                        [float(origen.latitud), float(origen.longitud)],
                        [float(destino.latitud), float(destino.longitud)],
                    ]

                tramos_para_crear.append(
                    TramoVial(
                        origen=origen,
                        destino=destino,
                        distancia_km=distancia_km,
                        tiempo_base_min=tiempo_base_min,
                        tipo_via=tipo_via,
                        geometria=geometria
                    )
                )

            TramoVial.objects.bulk_create(tramos_para_crear, batch_size=1000)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Red OSMnx importada correctamente."))
        self.stdout.write(f"Nodos creados: {nodos_creados}")
        self.stdout.write(f"Nodos actualizados: {nodos_actualizados}")
        self.stdout.write(f"Tramos creados: {len(tramos_para_crear)}")
        self.stdout.write(f"Tramos omitidos: {tramos_omitidos}")
        self.stdout.write("")
        self.stdout.write("Ahora los tramos guardan geometría real para dibujar mejor la ruta.")