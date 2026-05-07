from django.urls import path

from . import views

app_name = "tenancy"

urlpatterns = [
    path("configuracion/mapa/", views.TenantMapSettingsView.as_view(), name="map_settings"),
]
