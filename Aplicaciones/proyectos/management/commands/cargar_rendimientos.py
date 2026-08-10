from django.core.management.base import BaseCommand

from Aplicaciones.proyectos.models import RendimientoVehiculoTipo


class Command(BaseCommand):
    help = "Crea los rendimientos base que falten para cada tipo de vehículo"

    RENDIMIENTOS = {
        "AUTOMOVIL": 12.0,
        "TAXI": 11.0,
        "MOTOCICLETA": 30.0,
        "CAMION": 5.0,
        "CAMIONETA": 9.0,
    }

    def handle(self, *args, **options):
        creados = 0
        existentes = 0

        for tipo, km_l in self.RENDIMIENTOS.items():
            registro = (
                RendimientoVehiculoTipo.objects
                .filter(tipo=tipo)
                .order_by("pk")
                .first()
            )

            if registro is not None:
                existentes += 1
                self.stdout.write(
                    f"{tipo}: ya existe con {registro.km_l_promedio} km/L"
                )
                continue

            RendimientoVehiculoTipo.objects.create(
                tipo=tipo,
                km_l_promedio=km_l,
            )
            creados += 1
            self.stdout.write(
                f"{tipo}: creado con {km_l:.1f} km/L"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Rendimientos base verificados. "
                f"Creados: {creados}. Existentes: {existentes}."
            )
        )
