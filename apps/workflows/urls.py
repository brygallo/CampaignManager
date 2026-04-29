# Django
from django.urls import path

# Views
from .views import ChangeStateView

urlpatterns = [
    path(
        route="workflow/<slug:app>/<slug:model>/<int:pk>/change/",
        view=ChangeStateView.as_view(),
        name="workflow_change_state",
    ),
]
