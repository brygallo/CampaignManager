from django.urls import path

from . import views

app_name = "votes"

urlpatterns = [
    path("resultados-electorales/veedor/", views.ElectoralWatcherPanelView.as_view(), name="watcher"),
    path("resultados-electorales/reporte/", views.ElectoralReportView.as_view(), name="report"),
    path("resultados-electorales/reporte/datos/", views.ElectoralReportDataView.as_view(), name="report_data"),
    path("resultados-electorales/reporte/exportar.csv", views.ElectoralExportCsvView.as_view(), name="export_csv"),
    path(
        "resultados-electorales/reporte/exportar.<str:file_format>",
        views.ElectoralExportView.as_view(),
        name="export",
    ),
    path("resultados-electorales/buscar/", views.ElectoralLookupView.as_view(), name="lookup"),
]
