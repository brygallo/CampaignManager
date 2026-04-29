from django.urls import path

from . import views

urlpatterns = [
    path("switch-site/<int:site_id>/", views.switch_site, name="switch-site"),
]
