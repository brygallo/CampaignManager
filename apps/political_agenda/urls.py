from django.urls import path

from . import views

app_name = "political_agenda"

urlpatterns = [
    path(
        "agenda/calendario/",
        views.PoliticalAgendaCalendarView.as_view(),
        name="calendar",
    ),
    path(
        "agenda/calendario/datos/",
        views.PoliticalAgendaCalendarDataView.as_view(),
        name="calendar_data",
    ),
    path(
        "agenda/calendario/popup/<int:pk>/",
        views.PoliticalAgendaEventPopupView.as_view(),
        name="calendar_popup",
    ),
]
