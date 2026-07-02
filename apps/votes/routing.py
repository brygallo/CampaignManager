from django.urls import path

from . import consumers


websocket_urlpatterns = [
    path("ws/resultados-electorales/", consumers.ElectoralResultsConsumer.as_asgi()),
]
