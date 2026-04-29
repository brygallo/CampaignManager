# Django
from django.urls import path

# Views
from apps.insoles.views import (
    RenderFormView,
    RenderFieldView,
    RenderDetailView,
    RenderEditView,
)

urlpatterns = [
    path(
        route="insoles/forms/<slug:app>/<slug:model>/",
        view=RenderFormView.as_view(),
        name="insoles_form",
    ),
    path(
        route="insoles/forms/<slug:app>/<slug:model>/<slug:field>/",
        view=RenderFieldView.as_view(),
        name="insoles_field",
    ),
    path(
        route="insoles/detail/<slug:app>/<slug:model>/<slug:slug>/<slug:field>/",
        view=RenderDetailView.as_view(),
        name="insoles_detail",
    ),
    path(
        route="insoles/detail/<slug:app>/<slug:model>/<slug:slug>/<slug:field>/edit/",
        view=RenderEditView.as_view(),
        name="insoles_form_edit",
    ),
]
