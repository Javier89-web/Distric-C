from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from Aplicaciones.proyectos.ia_predictiva import entrenar_modelo_consumo


class Command(BaseCommand):
    help = "Entrena Random Forest para predecir consumo de combustible."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default=None,
            help="Ruta opcional a un CSV con datos reales o simulados.",
        )

    def handle(self, *args, **options):
        csv_path = options.get("csv_path")
        if csv_path and not Path(csv_path).exists():
            raise CommandError(f"No existe el archivo: {csv_path}")

        try:
            bundle = entrenar_modelo_consumo(dataset_path=csv_path, guardar=True)
        except Exception as error:
            raise CommandError(str(error)) from error

        metadata = bundle["metadata"]
        metricas = metadata.get("metricas", {})

        self.stdout.write(self.style.SUCCESS("Modelo Random Forest entrenado correctamente."))
        self.stdout.write(f"Versión: {metadata.get('version')}")
        self.stdout.write(f"Fuente: {metadata.get('fuente_datos')}")
        self.stdout.write(f"Registros: {metricas.get('registros')}")
        self.stdout.write(f"MAE: {metricas.get('mae_litros')} L")
        self.stdout.write(f"RMSE: {metricas.get('rmse_litros')} L")
        self.stdout.write(f"R²: {metricas.get('r2')}")
