"""URL routes for the active-campaign switcher."""
from django.urls import path

from apps.campaigns import views

app_name = "campaigns"

urlpatterns = [
    path(
        "campanas/activa/<int:pk>/",
        views.switch_active_campaign,
        name="switch_active",
    ),
    path(
        "campanas/activa/limpiar/",
        views.clear_active_campaign_view,
        name="clear_active",
    ),
]
