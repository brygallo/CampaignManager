from django.urls import path

from . import views

app_name = "field_surveys"

urlpatterns = [
    path(
        "levantamiento-campo/dashboard/", views.FieldSurveyDashboardView.as_view(), name="dashboard"
    ),
    path(
        "levantamiento-campo/dashboard/heatmap-datos/",
        views.FieldSurveyDashboardHeatmapDataView.as_view(),
        name="dashboard_heatmap_data",
    ),
    path("levantamiento-campo/mapa/", views.FieldSurveyMapView.as_view(), name="map"),
    path(
        "levantamiento-campo/mapa/datos/", views.FieldSurveyMapDataView.as_view(), name="map_data"
    ),
]
