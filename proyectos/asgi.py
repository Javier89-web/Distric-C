import os 
from django.core.asgi import get_asgi_application 
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyectos.settings') 

django_asgi_app = get_asgi_application() 

import Aplicaciones.proyectos.routing  

# Configura la aplicación ASGI
application = ProtocolTypeRouter({
    # Maneja solicitudes HTTP normales
    "http": django_asgi_app,

    # Maneja conexiones WebSocket
    "websocket": AuthMiddlewareStack(
        URLRouter(
            Aplicaciones.proyectos.routing.websocket_urlpatterns
        )
    ),
})
