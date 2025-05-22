from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/camera/(?P<camera_id>\w+)/stream/$', consumers.CameraStreamConsumer.as_asgi()),
    re_path(r'ws/camera/(?P<camera_id>\w+)/stats/$', consumers.CameraStatsConsumer.as_asgi()),
]