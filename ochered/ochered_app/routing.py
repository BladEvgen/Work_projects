from . import consumers
from django.urls import re_path

websocket_urlpatterns = [
    re_path(r'ws/queue/$', consumers.QueueConsumer.as_asgi()),  
    re_path(r'ws/queue/(?P<consultant_id>\d+)/$', consumers.QueueConsumer.as_asgi()),
]