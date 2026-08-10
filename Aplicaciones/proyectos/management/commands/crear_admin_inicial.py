import os

from django.core.management.base import BaseCommand
from Aplicaciones.proyectos.models import Usuario, Administrador


class Command(BaseCommand):
    help = "Crea o actualiza el administrador inicial configurado en variables de entorno"

    def handle(self, *args, **options):
        correo = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
        contrasena = os.environ.get("INITIAL_ADMIN_PASSWORD", "").strip()

        if not correo or not contrasena:
            self.stdout.write(
                self.style.WARNING(
                    "Administrador inicial omitido: faltan INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD."
                )
            )
            return

        usuario, creado = Usuario.objects.update_or_create(
            correo_usuario=correo,
            defaults={
                "cedula_usuario": os.environ.get("INITIAL_ADMIN_CEDULA", "1727663401").strip(),
                "nombre_usuario": os.environ.get("INITIAL_ADMIN_NOMBRE", "Javier").strip(),
                "apellido_usuario": os.environ.get("INITIAL_ADMIN_APELLIDO", "Administrador").strip(),
                "telefono_usuario": os.environ.get("INITIAL_ADMIN_TELEFONO", "0991287430").strip(),
                "contrasena_usuario": contrasena,
                "tiporol": "ADMINISTRADOR",
                "activo": True,
            },
        )

        Administrador.objects.update_or_create(
            usuario=usuario,
            defaults={
                "cargo": os.environ.get("INITIAL_ADMIN_CARGO", "Administrador General").strip(),
                "codigo_interno": os.environ.get("INITIAL_ADMIN_CODIGO", "ADM001").strip(),
                "telefono_institucional": os.environ.get("INITIAL_ADMIN_TELEFONO_INST", "0991287430").strip(),
            },
        )

        estado = "creado" if creado else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Administrador inicial {estado}: {usuario.correo_usuario}"))
