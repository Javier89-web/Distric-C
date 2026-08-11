import os

from django.core.management.base import BaseCommand
from Aplicaciones.proyectos.models import Usuario, Administrador


class Command(BaseCommand):
    help = "Crea o actualiza el administrador inicial sin generar duplicados."

    def handle(self, *args, **options):

        cedula = os.environ.get(
            "INITIAL_ADMIN_CEDULA",
            "1727663401"
        ).strip()

        correo = os.environ.get(
            "INITIAL_ADMIN_EMAIL",
            "javier_admin@distric.com"
        ).strip()

        contrasena = os.environ.get(
            "INITIAL_ADMIN_PASSWORD",
            ""
        ).strip()

        if not correo or not contrasena:
            self.stdout.write(
                self.style.WARNING(
                    "No se configuró INITIAL_ADMIN_EMAIL "
                    "o INITIAL_ADMIN_PASSWORD."
                )
            )
            return

        # Primero buscar por cédula porque es un campo único
        usuario = Usuario.objects.filter(
            cedula_usuario=cedula
        ).first()

        # Si no existe por cédula, intentar por correo
        if not usuario:
            usuario = Usuario.objects.filter(
                correo_usuario=correo
            ).first()

        if usuario:
            usuario.cedula_usuario = cedula
            usuario.nombre_usuario = os.environ.get(
                "INITIAL_ADMIN_NOMBRE",
                "Javier"
            )
            usuario.apellido_usuario = os.environ.get(
                "INITIAL_ADMIN_APELLIDO",
                "Pilco"
            )
            usuario.telefono_usuario = os.environ.get(
                "INITIAL_ADMIN_TELEFONO",
                "0991287430"
            )
            usuario.correo_usuario = correo
            usuario.contrasena_usuario = contrasena
            usuario.tiporol = "ADMINISTRADOR"
            usuario.activo = True

            usuario.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador existente actualizado: {correo}"
                )
            )

        else:
            usuario = Usuario.objects.create(
                cedula_usuario=cedula,
                nombre_usuario=os.environ.get(
                    "INITIAL_ADMIN_NOMBRE",
                    "Javier"
                ),
                apellido_usuario=os.environ.get(
                    "INITIAL_ADMIN_APELLIDO",
                    "Pilco"
                ),
                correo_usuario=correo,
                telefono_usuario=os.environ.get(
                    "INITIAL_ADMIN_TELEFONO",
                    "0991287430"
                ),
                contrasena_usuario=contrasena,
                tiporol="ADMINISTRADOR",
                activo=True
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador inicial creado: {correo}"
                )
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