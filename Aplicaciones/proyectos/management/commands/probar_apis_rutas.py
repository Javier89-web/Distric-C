from django.core.management.base import BaseCommand

from Aplicaciones.proyectos.servicios_contexto_ruta import (
    buscar_lugares_google,
    obtener_factores_ruta,
)


class Command(BaseCommand):
    help = "Comprueba Places, Routes/Traffic y Weather, indicando la fuente real o el respaldo utilizado."

    def add_arguments(self, parser):
        parser.add_argument("--query", default="Maltería Mall Latacunga")
        parser.add_argument("--origen-lat", type=float, default=-0.9175)
        parser.add_argument("--origen-lon", type=float, default=-78.6331)
        parser.add_argument("--destino-lat", type=float, default=-0.9258)
        parser.add_argument("--destino-lon", type=float, default=-78.6259)

    def handle(self, *args, **options):
        places = buscar_lugares_google(
            options["query"],
            lat=options["origen_lat"],
            lon=options["origen_lon"],
        )
        self.stdout.write(self.style.MIGRATE_HEADING("BÚSQUEDA DE DESTINOS"))
        self.stdout.write(f"OK: {places.get('ok')}")
        self.stdout.write(f"Fuente: {places.get('fuente', 'sin fuente')}")
        self.stdout.write(f"Mensaje: {places.get('mensaje')}")
        self.stdout.write(f"Resultados: {len(places.get('resultados', []))}")

        factors = obtener_factores_ruta(
            options["origen_lat"],
            options["origen_lon"],
            options["destino_lat"],
            options["destino_lon"],
        )
        for title, key in (("TRÁFICO", "trafico"), ("CLIMA", "clima")):
            data = factors[key]
            self.stdout.write(self.style.MIGRATE_HEADING(title))
            self.stdout.write(f"Fuente: {data.get('fuente')}")
            self.stdout.write(f"API disponible: {data.get('api_disponible')}")
            self.stdout.write(f"Descripción: {data.get('descripcion_trafico') or data.get('descripcion_clima')}")
            self.stdout.write(f"Factor: {data.get('factor_trafico') or data.get('factor_clima')}")
            self.stdout.write(f"Mensaje: {data.get('mensaje')}")
