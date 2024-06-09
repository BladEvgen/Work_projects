import os
import django


import ochered_app.routing
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

django.setup()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_settings.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(ochered_app.routing.websocket_urlpatterns)
        ),
    }
)
