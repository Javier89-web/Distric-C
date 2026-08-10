from django.core.management.base import BaseCommand
from django.core.management import call_command

from Aplicaciones.proyectos.models import NodoMapa, TramoVial


class Command(BaseCommand):
    help = "Carga la red vial de Latacunga solo si la base de datos está vacía."

    def handle(self, *args, **options):
        total_nodos = NodoMapa.objects.count()
        total_tramos = TramoVial.objects.count()

        if total_nodos > 0 and total_tramos > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Red vial ya cargada: {total_nodos} nodos y {total_tramos} tramos."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                "No existe red vial en la base. Iniciando importación..."
            )
        )

        call_command(
            "importar_red_osmnx",
            "scripts_osmnx/latacunga_osmnx.json",
            limpiar=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Red vial lista: {NodoMapa.objects.count()} nodos y "
                f"{TramoVial.objects.count()} tramos."
            )
        )
