"""Select2 endpoint with dependent-fields support."""
from django.urls import path

from .views import AutoResponseView

app_name = "django_select2"

urlpatterns = [
    path("fields/auto.json", AutoResponseView.as_view(), name="auto-json"),
]
