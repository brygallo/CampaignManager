from apps.reporting.exporters import ReportColumn, TabularReport

from .models import ElectoralResultLine


def electoral_results_report():
    rows = ElectoralResultLine.objects.select_related(
        "report__parish",
        "report__venue",
        "report__table",
        "report__dignity",
        "report__district",
    )
    return TabularReport(
        title="Resultados electorales",
        filename="resultados-electorales",
        sheet_name="Resultados",
        columns=(
            ReportColumn("Parroquia", "report.parish.name", width=24),
            ReportColumn("Recinto", "report.venue.name", width=32),
            ReportColumn("Mesa", "report.table.number", width=12),
            ReportColumn("Dignidad", "report.dignity.name", width=24),
            ReportColumn("Circunscripción", "report.district.name", width=24),
            ReportColumn("Lista", "list_code", width=12),
            ReportColumn("Candidato", "candidate_name", width=32),
            ReportColumn("Votos", "votes", width=12),
        ),
        rows=rows,
    )
