import os

from django.core.management.base import BaseCommand
from Aplicaciones.proyectos.models import Usuario, Administrador


class Command(BaseCommand):
    help = "Crea o actualiza el administrador inicial del sistema"

    def handle(self, *args, **options):

        correo = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
        contrasena = os.environ.get("INITIAL_ADMIN_PASSWORD", "").strip()

        if not correo or not contrasena:
            self.stdout.write(
                self.style.WARNING(
                    "No se configuró INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD."
                )
            )
            return

        usuario, creado = Usuario.objects.update_or_create(
            correo_usuario=correo,
            defaults={
                "cedula_usuario": os.environ.get(
                    "INITIAL_ADMIN_CEDULA",
                    "1727663401"
                ),
                "nombre_usuario": os.environ.get(
                    "INITIAL_ADMIN_NOMBRE",
                    "Javier"
                ),
                "apellido_usuario": os.environ.get(
                    "INITIAL_ADMIN_APELLIDO",
                    "Pilco"
                ),
                "telefono_usuario": os.environ.get(
                    "INITIAL_ADMIN_TELEFONO",
                    "0991287430"
                ),
                "contrasena_usuario": contrasena,
                "tiporol": "ADMINISTRADOR",
                "activo": True,
            }
        )

        Administrador.objects.update_or_create(
            usuario=usuario,
            defaults={
                "cargo": os.environ.get(
                    "INITIAL_ADMIN_CARGO",
                    "Administrador General"
                ),
                "codigo_interno": os.environ.get(
                    "INITIAL_ADMIN_CODIGO",
                    "ADM001"
                ),
                "telefono_institucional": os.environ.get(
                    "INITIAL_ADMIN_TELEFONO_INST",
                    "0991287430"
                ),
            }
        )

        if creado:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador creado: {usuario.correo_usuario}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador actualizado: {usuario.correo_usuario}"
                )
            )