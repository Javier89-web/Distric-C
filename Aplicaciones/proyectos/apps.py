from django.apps import AppConfig


class ProyectosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Aplicaciones.proyectos'

    def ready(self):
        import Aplicaciones.proyectos.signals

