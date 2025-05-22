from django.urls import path, include
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from cameras.routing import websocket_urlpatterns as camera_websockets

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('', URLRouter(camera_websockets)),
        ])
    ),
})