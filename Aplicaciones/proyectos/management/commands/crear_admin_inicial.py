import os

from django.core.management.base import BaseCommand
from Aplicaciones.proyectos.models import Usuario, Administrador


class Command(BaseCommand):
    help = "Crea o actualiza el administrador inicial sin generar duplicados"

    def handle(self, *args, **options):
        cedula = os.environ.get("INITIAL_ADMIN_CEDULA", "1727663401").strip()
        correo = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
        contrasena = os.environ.get("INITIAL_ADMIN_PASSWORD", "").strip()

        if not correo or not contrasena:
            self.stdout.write(
                self.style.WARNING(
                    "Administrador inicial omitido: faltan INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD."
                )
            )
            return

        # La cédula y el correo son únicos. Buscamos primero por cédula para
        # reutilizar el registro ya existente en bases de datos de producción.
        usuario = Usuario.objects.filter(cedula_usuario=cedula).first()
        if usuario is None:
            usuario = Usuario.objects.filter(correo_usuario=correo).first()

        creado = usuario is None
        if creado:
            usuario = Usuario(cedula_usuario=cedula)

        usuario.cedula_usuario = cedula
        usuario.nombre_usuario = os.environ.get("INITIAL_ADMIN_NOMBRE", "Javier").strip()
        usuario.apellido_usuario = os.environ.get("INITIAL_ADMIN_APELLIDO", "Administrador").strip()
        usuario.telefono_usuario = os.environ.get("INITIAL_ADMIN_TELEFONO", "0991287430").strip()
        usuario.correo_usuario = correo
        usuario.contrasena_usuario = contrasena
        usuario.tiporol = "ADMINISTRADOR"
        usuario.activo = True
        usuario.save()

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
