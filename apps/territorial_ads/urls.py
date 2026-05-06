from django.urls import path

from . import views

app_name = "territorial_ads"

urlpatterns = [
    path("publicidad-territorial/mapa/", views.PhysicalAdMapView.as_view(), name="map"),
    path("publicidad-territorial/mapa/datos/", views.PhysicalAdMapDataView.as_view(), name="map_data"),
    path("publicidad-territorial/mapa/popup/<int:pk>/", views.PhysicalAdMapPopupView.as_view(), name="map_popup"),
]
