"""Select2 endpoint with dependent-fields support."""
from django.urls import path

from .views import AutoResponseView

urlpatterns = [
    path("fields/auto.json", AutoResponseView.as_view(), name="auto-json"),
]
