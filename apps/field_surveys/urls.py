from django.urls import path

from . import views

app_name = "field_surveys"

urlpatterns = [
    path("levantamiento-campo/nuevo/", views.FieldSurveyQuickCreateView.as_view(), name="survey_create"),
    path("levantamiento-campo/dashboard/", views.FieldSurveyDashboardView.as_view(), name="dashboard"),
    path("levantamiento-campo/mapa/", views.FieldSurveyMapView.as_view(), name="map"),
    path("levantamiento-campo/mapa/datos/", views.FieldSurveyMapDataView.as_view(), name="map_data"),
]
