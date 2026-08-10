import csv
import math
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from Aplicaciones.proyectos.models import RendimientoVehiculoTipo, TramoViaje


HEADERS = [
    "distancia_km",
    "tiempo_min",
    "velocidad_kmh",
    "carga_kg",
    "peso_vehiculo_kg",
    "capacidad_kg",
    "cilindraje_l",
    "rendimiento_km_l",
    "factor_trafico",
    "factor_clima",
    "hora_sin",
    "hora_cos",
    "tipo_via_codigo",
    "detenciones_estimadas",
    "pendiente_pct",
    "consumo_base_l",
    "consumo_real_l",
    "fuente",
]

TIPO_VIA = {"PRINCIPAL": 0, "RURAL": 1, "URBANA": 2, "SECUNDARIA": 3}


class Command(BaseCommand):
    help = "Exporta tramos con consumo real a un CSV compatible con Random Forest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--salida",
            default="consumos_reales_distric_c.csv",
            help="Ruta del CSV de salida.",
        )

    def handle(self, *args, **options):
        salida = Path(options["salida"]).expanduser().resolve()
        tramos = (
            TramoViaje.objects
            .filter(estado="COMPLETADO", consumo_real_l__isnull=False)
            .select_related("viaje__vehiculo")
            .order_by("fecha_fin")
        )

        filas = []
        for tramo in tramos:
            vehiculo = tramo.viaje.vehiculo
            rendimiento = RendimientoVehiculoTipo.objects.filter(
                tipo=vehiculo.tipovehiculo_vehiculo
            ).first()
            rendimiento_km_l = float(rendimiento.km_l_promedio) if rendimiento else 10.0
            distancia = float(tramo.distancia_real_km or tramo.distancia_estimada_km or 0)
            tiempo = float(tramo.tiempo_real_min or tramo.tiempo_estimado_min or 0)
            if distancia <= 0 or tiempo <= 0 or rendimiento_km_l <= 0:
                continue

            detalle = tramo.detalle_prediccion or {}
            tipo_via = str(detalle.get("tipo_via_dominante") or "URBANA")
            detenciones = float(detalle.get("detenciones_estimadas") or 0)
            fecha = tramo.fecha_inicio or tramo.fecha_creacion
            hora = fecha.hour if fecha else 12
            angulo = 2 * math.pi * hora / 24.0

            filas.append({
                "distancia_km": round(distancia, 5),
                "tiempo_min": round(tiempo, 5),
                "velocidad_kmh": round(distancia / tiempo * 60.0, 5),
                "carga_kg": float(tramo.carga_inicio_kg),
                "peso_vehiculo_kg": float(vehiculo.peso_auto or 0) * 1000.0,
                "capacidad_kg": float(vehiculo.capacidad_carga_kg or 1),
                "cilindraje_l": float(vehiculo.cilindraje or 0),
                "rendimiento_km_l": rendimiento_km_l,
                "factor_trafico": float(tramo.trafico_factor or 1),
                "factor_clima": float(tramo.clima_factor or 1),
                "hora_sin": round(math.sin(angulo), 5),
                "hora_cos": round(math.cos(angulo), 5),
                "tipo_via_codigo": TIPO_VIA.get(tipo_via, 2),
                "detenciones_estimadas": detenciones,
                "pendiente_pct": 0.0,
                "consumo_base_l": round(distancia / rendimiento_km_l, 6),
                "consumo_real_l": float(tramo.consumo_real_l),
                "fuente": "REAL_DISTRIC_C",
            })

        if not filas:
            raise CommandError(
                "No existen tramos completados con consumo real registrado."
            )

        salida.parent.mkdir(parents=True, exist_ok=True)
        with salida.open("w", encoding="utf-8", newline="") as archivo:
            writer = csv.DictWriter(archivo, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(filas)

        self.stdout.write(self.style.SUCCESS(
            f"Se exportaron {len(filas)} registros reales en: {salida}"
        ))
