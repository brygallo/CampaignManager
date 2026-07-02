from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
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


def build_electoral_report_payload(filters=None):
    filters = filters or {}
    reports = ElectoralResultReport.objects.select_related(
        "parish", "venue", "table", "dignity", "district", "watcher"
    )
    if filters.get("dignity"):
        reports = reports.filter(dignity=filters["dignity"])
    if filters.get("district"):
        reports = reports.filter(district=filters["district"])
    if filters.get("parish"):
        reports = reports.filter(parish=filters["parish"])
    if filters.get("venue"):
        reports = reports.filter(venue=filters["venue"])
    if filters.get("table"):
        reports = reports.filter(table=filters["table"])

    lines = ElectoralResultLine.objects.filter(report__in=reports)
    summary_rows = list(
        lines.values("line_type", "list_code", "candidate_name")
        .annotate(votes=Sum("votes"))
        .order_by("-votes", "list_code", "candidate_name")
    )
    total_votes = sum(row["votes"] or 0 for row in summary_rows)
    for row in summary_rows:
        votes = row["votes"] or 0
        row["percent"] = round((votes * 100 / total_votes), 1) if total_votes else 0
        row["label"] = row["list_code"]
        if row["candidate_name"]:
            row["label"] = f"{row['list_code']} - {row['candidate_name']}"

    latest = []
    for report in reports.prefetch_related("lines").order_by("-created_date")[:20]:
        for line in report.lines.all().order_by("order", "list_code"):
            latest.append(
                {
                    "parish": report.parish.name,
                    "venue": report.venue.name,
                    "table": report.table.number,
                    "gender": report.table.get_gender_display(),
                    "dignity": report.dignity.name,
                    "district": report.district.name,
                    "status": report.get_status_display(),
                    "list": line.list_code,
                    "candidate": line.candidate_name,
                    "votes": line.votes,
                }
            )
    return {
        "total_votes": total_votes,
        "dignities_count": reports.values("dignity").distinct().count(),
        "lists_count": lines.values("list_code").distinct().count(),
        "summary_rows": summary_rows,
        "chart": {
            "categories": [row["label"] for row in summary_rows],
            "series": [row["votes"] or 0 for row in summary_rows],
        },
        "latest": latest[:30],
    }


def broadcast_electoral_report_update():
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        "electoral_results",
        {
            "type": "electoral_results_updated",
            "payload": build_electoral_report_payload(),
        },
    )


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
        form = ElectoralWatcherForm(request.POST, watcher=request.user)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        report = self._save_report(form)
        messages.success(request, f"Acta registrada para {report.table}.")
        broadcast_electoral_report_update()
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
        context.update(
            {
                "form": form,
                "payload": build_electoral_report_payload(filters),
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
        return JsonResponse(build_electoral_report_payload(filters))


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


class ElectoralMapView(LoginRequiredMixin, TemplateView):
    template_name = "votes/map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Mapa veedores"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Resultados electorales", None),
            ("Mapa veedores", None),
        ]
        context["form"] = ElectoralReportFilterForm(self.request.GET or None)
        return context


class ElectoralMapDataView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = ElectoralReportFilterForm(request.GET or None)
        filters = {}
        if form.is_valid():
            filters = {key: value for key, value in form.cleaned_data.items() if value}

        venues = ElectoralVenue.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).select_related("parish__canton__province")
        if filters.get("parish"):
            venues = venues.filter(parish=filters["parish"])
        if filters.get("venue"):
            venues = venues.filter(pk=filters["venue"].pk)

        reports = ElectoralResultReport.objects.filter(venue__in=venues)
        if filters.get("dignity"):
            reports = reports.filter(dignity=filters["dignity"])
        if filters.get("district"):
            reports = reports.filter(district=filters["district"])
        if filters.get("table"):
            reports = reports.filter(table=filters["table"])

        table_counts = {
            row["venue_id"]: row["count"]
            for row in ElectoralTable.objects.filter(venue__in=venues, is_active=True)
            .values("venue_id")
            .annotate(count=Count("id"))
        }
        report_counts = {
            row["venue_id"]: row["count"]
            for row in reports.values("venue_id").annotate(count=Count("id", distinct=True))
        }
        vote_counts = {
            row["report__venue_id"]: row["votes"] or 0
            for row in ElectoralResultLine.objects.filter(report__in=reports)
            .values("report__venue_id")
            .annotate(votes=Sum("votes"))
        }

        points = []
        for venue in venues.order_by("parish__name", "name"):
            tables = table_counts.get(venue.pk, 0)
            received = report_counts.get(venue.pk, 0)
            pending = max(tables - received, 0)
            if received == 0:
                status = "pending"
                color = "#f1416c"
                label = "Sin actas"
            elif pending > 0:
                status = "partial"
                color = "#ffc700"
                label = "Parcial"
            else:
                status = "complete"
                color = "#50cd89"
                label = "Completo"
            points.append(
                {
                    "id": venue.pk,
                    "name": venue.name,
                    "parish": venue.parish.name,
                    "canton": venue.parish.canton.name,
                    "province": venue.parish.canton.province.name,
                    "lat": float(venue.latitude),
                    "lng": float(venue.longitude),
                    "tables": tables,
                    "reports": received,
                    "pending": pending,
                    "votes": vote_counts.get(venue.pk, 0),
                    "status": status,
                    "status_label": label,
                    "color": color,
                }
            )
        return JsonResponse({"points": points, "count": len(points)})


class ElectoralExportView(LoginRequiredMixin, ReportExportView):
    file_format = "csv"

    def get_report(self):
        return electoral_results_report()


class ElectoralExportCsvView(ElectoralExportView):
    file_format = "csv"
