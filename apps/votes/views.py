from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.reporting.views import ReportExportView

from .forms import (
    ElectoralReportFilterForm,
    ElectoralWatcherForm,
    electoral_districts_for_parish,
    resolve_electoral_district,
)
from .models import (
    ElectoralDignity,
    ElectoralDistrict,
    ElectoralResultLine,
    ElectoralResultReport,
    ElectoralTable,
    ElectoralTableAssignment,
    ElectoralVenue,
)
from .reports import electoral_results_report
from .services import ElectoralReportConsistencyService, ElectoralReportDashboardService


class ElectoralWatcherPanelView(LoginRequiredMixin, TemplateView):
    template_name = "votes/watcher.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form") or ElectoralWatcherForm(watcher=self.request.user)
        assignments = (
            ElectoralTableAssignment.objects.filter(watcher=self.request.user, is_active=True)
            .select_related("table__venue__parish__canton__province")
            .order_by("table__venue__parish__name", "table__venue__name", "table__number")
        )
        context.update(
            {
                "form": form,
                "assignments": assignments,
                "candidate_options": getattr(form, "candidate_options", []),
                "latest_reports": self._latest_reports(),
                "page_title": "Validación de mesas",
                "breadcrumbs": [
                    ("Inicio", "/"),
                    ("Resultados electorales", None),
                    ("Veedor", None),
                ],
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        form = ElectoralWatcherForm(request.POST, request.FILES, watcher=request.user)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        alerts = ElectoralReportConsistencyService(form).build_alerts()
        report = self._save_report(form)
        messages.success(request, f"Acta registrada para {report.table}.")
        for alert in alerts:
            messages.warning(request, alert)
        ElectoralReportDashboardService.broadcast_update()
        return HttpResponseRedirect(reverse("votes:watcher"))

    def _save_report(self, form):
        cleaned = form.cleaned_data
        report, _ = ElectoralResultReport.objects.update_or_create(
            table=cleaned["table"],
            dignity=cleaned["dignity"],
            district=form.district,
            defaults={
                "parish": cleaned["parish"],
                "venue": cleaned["venue"],
                "watcher": self.request.user,
                "status": ElectoralResultReport.Status.SUBMITTED,
                "voters_count": cleaned.get("voters_count"),
                "is_active": True,
            },
        )
        if cleaned.get("evidence_file"):
            report.evidence_file = cleaned["evidence_file"]
            report.save(update_fields=["evidence_file"])
        report.lines.all().delete()
        order = 1
        for option in form.candidate_options:
            ElectoralResultLine.objects.create(
                report=report,
                line_type=ElectoralResultLine.LineType.CANDIDATE,
                candidate_option=option,
                list_code=option.list_code,
                candidate_name=option.candidate_name,
                votes=cleaned.get(form.vote_field_name(option)) or 0,
                order=order,
            )
            order += 1
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.BLANK,
            list_code="BLANCOS",
            votes=cleaned["blank_votes"],
            order=order,
        )
        ElectoralResultLine.objects.create(
            report=report,
            line_type=ElectoralResultLine.LineType.NULL,
            list_code="NULOS",
            votes=cleaned["null_votes"],
            order=order + 1,
        )
        return report

    def _latest_reports(self):
        return (
            ElectoralResultReport.objects.select_related(
                "parish", "venue", "table", "dignity", "district", "watcher"
            )
            .prefetch_related("lines")
            .order_by("-created_date")[:10]
        )


class ElectoralReportView(LoginRequiredMixin, TemplateView):
    template_name = "votes/report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = ElectoralReportFilterForm(self.request.GET or None)
        filters = {}
        if form.is_valid():
            filters = {key: value for key, value in form.cleaned_data.items() if value}
        dashboard_service = ElectoralReportDashboardService(filters)
        context.update(
            {
                "form": form,
                "payload": dashboard_service.build_payload(),
                "dignity_tabs": dashboard_service.build_dignity_tabs(self.request.GET),
                "page_title": "Reporte veedores",
                "breadcrumbs": [
                    ("Inicio", "/"),
                    ("Resultados electorales", None),
                    ("Reporte veedores", None),
                ],
            }
        )
        return context


class ElectoralReportDataView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = ElectoralReportFilterForm(request.GET or None)
        filters = {}
        if form.is_valid():
            filters = {key: value for key, value in form.cleaned_data.items() if value}
        return JsonResponse(ElectoralReportDashboardService(filters).build_payload())


class ElectoralLookupView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        lookup = request.GET.get("lookup")
        if lookup == "venues":
            rows = ElectoralVenue.objects.filter(
                parish_id=request.GET.get("parish"), is_active=True
            ).order_by("name")
            return JsonResponse({"results": [{"id": row.pk, "text": row.name} for row in rows]})
        if lookup == "tables":
            rows = ElectoralTable.objects.filter(
                venue_id=request.GET.get("venue"), is_active=True
            ).order_by("number", "gender")
            return JsonResponse(
                {"results": [{"id": row.pk, "text": f"{row.number} - {row.get_gender_display()}"} for row in rows]}
            )
        if lookup == "dignities":
            rows = self._dignities_for_parish(request.GET.get("parish"))
            return JsonResponse({"results": [{"id": row.pk, "text": row.name} for row in rows]})
        if lookup == "candidates":
            district = resolve_electoral_district(
                parish_id=request.GET.get("parish"), dignity_id=request.GET.get("dignity")
            )
            rows = []
            if district:
                rows = district.candidate_options.filter(is_active=True).order_by(
                    "order", "list_code", "candidate_name"
                )
            return JsonResponse(
                {
                    "district": {"id": district.pk, "text": district.name} if district else None,
                    "results": [
                        {"id": row.pk, "list": row.list_code, "candidate": row.candidate_name}
                        for row in rows
                    ],
                }
            )
        return JsonResponse({"results": []})

    def _dignities_for_parish(self, parish_id):
        from apps.locations.models import Parish

        try:
            parish = Parish.objects.select_related("canton__province").get(pk=parish_id)
        except (Parish.DoesNotExist, ValueError, TypeError):
            return ElectoralDignity.objects.none()
        districts = electoral_districts_for_parish(parish)
        return ElectoralDignity.objects.filter(districts__in=districts, is_active=True).distinct().order_by(
            "order", "name"
        )


class ElectoralExportView(LoginRequiredMixin, ReportExportView):
    file_format = "csv"

    def get_report(self):
        return electoral_results_report()


class ElectoralExportCsvView(ElectoralExportView):
    file_format = "csv"
