from django.urls import path

from . import views

app_name = "territorial_ads"

urlpatterns = [
    path("publicidad-territorial/mapa/", views.PhysicalAdMapView.as_view(), name="map"),
    path("publicidad-territorial/mapa/datos/", views.PhysicalAdMapDataView.as_view(), name="map_data"),
    path("publicidad-territorial/mapa/popup/<int:pk>/", views.PhysicalAdMapPopupView.as_view(), name="map_popup"),
    path(
        "publicidad-territorial/asignacion-masiva/",
        views.PhysicalAdBulkAssignView.as_view(),
        name="bulk_assign",
    ),
    path(
        "publicidad-territorial/mapa/instalacion-directa/crear/",
        views.DirectInstallCreateView.as_view(),
        name="direct_install_create",
    ),
    path(
        "publicidad-territorial/publicidad/<int:pk>/accion/<str:name>/",
        views.PhysicalAdUnitActionView.as_view(),
        name="unit_action",
    ),
    path(
        "publicidad-territorial/solicitud/<int:pk>/asignar-instalador-todas/",
        views.PhysicalAdAssignAllInstallersView.as_view(),
        name="assign_all_installers",
    ),
    path(
        "publicidad-territorial/mapa/rechazo/crear/",
        views.AdvertisingRefusalCreateView.as_view(),
        name="refusal_create",
    ),
    path(
        "publicidad-territorial/mapa/rechazo/popup/<int:pk>/",
        views.AdvertisingRefusalPopupView.as_view(),
        name="refusal_popup",
    ),
]
