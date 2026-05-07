from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.campaigns.models import Campaign

from .models import (
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyResultOption,
)


# Primary result code → map pin color mapping.
RESULT_COLORS = {
    "APOYA": "#50cd89",
    "INDECISO": "#ffc700",
    "NO_APOYA": "#f1416c",
    "ATENDIO": "#3e97ff",
    "NO_ATENDIO": "#7e8299",
}
DEFAULT_VISIT_COLOR = "#3e97ff"


def can_view_all_field_surveys(user):
    return user.is_superuser or user.is_staff or user.has_perm("field_surveys.view_all_fieldsurvey")


def fieldsurvey_queryset_for_user(user):
    queryset = (
        FieldSurvey.objects.select_related("campaign", "brigadier", "created_by")
        .prefetch_related("results", "competitor_advertising_detections")
        .all()
    )
    if not can_view_all_field_surveys(user):
        queryset = queryset.filter(brigadier=user)
    return queryset


def fieldsurvey_list_url():
    return reverse("site:field_surveys_fieldsurvey_listar")


def fieldsurvey_detail_url(pk):
    return reverse("site:field_surveys_fieldsurvey_", kwargs={"pk": pk})


def competitor_detection_detail_url(pk):
    return reverse("site:field_surveys_competitoradvertisingdetection_", kwargs={"pk": pk})


class FieldSurveySpecialViewMixin(LoginRequiredMixin):
    def get_queryset(self):
        return fieldsurvey_queryset_for_user(self.request.user)


class FieldSurveyFilterMixin:
    def apply_filters(self, queryset):
        params = self.request.GET
        if params.get("campaign"):
            queryset = queryset.filter(campaign_id=params["campaign"])
        if params.get("brigadier") and can_view_all_field_surveys(self.request.user):
            queryset = queryset.filter(brigadier_id=params["brigadier"])
        if params.get("result"):
            queryset = queryset.filter(results__id=params["result"])
        if params.get("date_from"):
            queryset = queryset.filter(created_date__date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(created_date__date__lte=params["date_to"])
        return queryset.distinct()

    def filtered_queryset(self):
        return self.apply_filters(self.get_queryset())


class FieldSurveyAccessMixin(FieldSurveySpecialViewMixin):
    pass


class FieldSurveyDashboardView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, TemplateView):
    template_name = "field_surveys/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        surveys = self.filtered_queryset()
        competitor_ads = CompetitorAdvertisingDetection.objects.filter(field_survey__in=surveys)
        if not can_view_all_field_surveys(self.request.user):
            competitor_ads = competitor_ads.filter(brigadier=self.request.user)

        context.update(get_filter_context(self.request))
        context["can_view_all"] = can_view_all_field_surveys(self.request.user)
        result_counts = surveys.aggregate(
            total_visits=Count("id", distinct=True),
            total_voters=Sum("voters_count"),
            support=Count("id", filter=Q(results__code="APOYA"), distinct=True),
            undecided=Count("id", filter=Q(results__code="INDECISO"), distinct=True),
            not_support=Count("id", filter=Q(results__code="NO_APOYA"), distinct=True),
            attended=Count("id", filter=Q(results__code="ATENDIO"), distinct=True),
            not_attended=Count("id", filter=Q(results__code="NO_ATENDIO"), distinct=True),
        )
        context["metrics"] = {
            "total_visits": result_counts["total_visits"] or 0,
            "total_voters": result_counts["total_voters"] or 0,
            "support": result_counts["support"] or 0,
            "undecided": result_counts["undecided"] or 0,
            "not_support": result_counts["not_support"] or 0,
            "competitor_ads": competitor_ads.count(),
        }
        ranking = list(
            surveys.values(
                "brigadier_id",
                "brigadier__first_name",
                "brigadier__last_name",
                "brigadier__username",
            )
            .annotate(visits=Count("id"), voters=Sum("voters_count"))
            .order_by("-visits", "-voters")[:10]
        )
        max_visits = max((row["visits"] for row in ranking), default=0)
        for row in ranking:
            row["progress"] = (
                int(round((row["visits"] / max_visits) * 100)) if max_visits else 0
            )
            row["voters"] = row["voters"] or 0
        context["brigadier_ranking"] = ranking

        result_distribution = build_result_distribution(result_counts)
        context["result_distribution"] = result_distribution

        visits_trend = build_visits_trend(self.request, surveys)
        competitor_ads_breakdown = build_competitor_breakdown(competitor_ads)
        context["competitor_ads_breakdown"] = competitor_ads_breakdown

        context["chart_data"] = {
            "results": [
                {"label": item["label"], "value": item["value"], "color": item["color"]}
                for item in result_distribution
            ],
            "trend": visits_trend,
        }
        return context


class FieldSurveyDashboardHeatmapDataView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, View):
    """Return density points for the dashboard heatmap, grouped by layer.

    Honors the dashboard filters via FieldSurveyFilterMixin and returns three
    layers: APOYA (support), INDECISO (undecided) and competitor advertising
    detections. Each layer is a list of [lat, lng, weight] tuples plus a count.
    """

    def _survey_points(self, base_qs, result_code):
        rows = (
            base_qs.filter(results__code=result_code)
            .values_list("latitude", "longitude", "voters_count")
            .distinct()
        )
        points = []
        for lat, lng, voters in rows:
            if lat is None or lng is None:
                continue
            weight = float(voters) if voters else 1.0
            points.append([float(lat), float(lng), weight])
        return points

    def get(self, request, *args, **kwargs):
        surveys = self.filtered_queryset()

        competitor_ads = CompetitorAdvertisingDetection.objects.filter(
            field_survey__in=surveys
        )
        if not can_view_all_field_surveys(request.user):
            competitor_ads = competitor_ads.filter(brigadier=request.user)

        competitor_points = []
        for lat, lng in competitor_ads.values_list("latitude", "longitude"):
            if lat is None or lng is None:
                continue
            competitor_points.append([float(lat), float(lng), 1.0])

        layers = {
            "apoyo": {
                "label": "Apoyo",
                "color": RESULT_COLORS["APOYA"],
                "points": self._survey_points(surveys, "APOYA"),
            },
            "indecisos": {
                "label": "Indecisos",
                "color": RESULT_COLORS["INDECISO"],
                "points": self._survey_points(surveys, "INDECISO"),
            },
            "competencia": {
                "label": "Competencia",
                "color": "#d9214e",
                "points": competitor_points,
            },
        }
        for layer in layers.values():
            layer["count"] = len(layer["points"])

        total = sum(layer["count"] for layer in layers.values())

        # Legacy shape for callers that still expect a flat point list (combined).
        combined = (
            layers["apoyo"]["points"]
            + layers["indecisos"]["points"]
            + layers["competencia"]["points"]
        )
        return JsonResponse(
            {
                "layers": layers,
                "total": total,
                "points": combined,
                "count": total,
            }
        )


class FieldSurveyMapView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "field_surveys/map.html"
    permission_required = "field_surveys.view_fieldsurvey"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_filter_context(self.request))
        context["can_view_all"] = can_view_all_field_surveys(self.request.user)
        context["competitors"] = Competitor.objects.filter(is_active=True).order_by(
            "campaign__name", "list_number", "political_organization"
        )
        return context


class FieldSurveyMapDataView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, View):
    def get(self, request, *args, **kwargs):
        surveys = self.filtered_queryset().select_related("campaign", "brigadier")
        competitor_ads = CompetitorAdvertisingDetection.objects.select_related(
            "competitor", "campaign", "brigadier", "advertising_type"
        )
        if not can_view_all_field_surveys(request.user):
            competitor_ads = competitor_ads.filter(brigadier=request.user)
        if request.GET.get("campaign"):
            competitor_ads = competitor_ads.filter(campaign_id=request.GET["campaign"])
        if request.GET.get("competitor"):
            competitor_ads = competitor_ads.filter(competitor_id=request.GET["competitor"])
        # Apply the same temporal window as surveys so the map stays coherent
        # when the user filters by date range (#A12).
        if request.GET.get("date_from"):
            competitor_ads = competitor_ads.filter(created_date__date__gte=request.GET["date_from"])
        if request.GET.get("date_to"):
            competitor_ads = competitor_ads.filter(created_date__date__lte=request.GET["date_to"])

        visits = []
        for survey in surveys:
            result_code = survey.primary_result_code
            visits.append(
                {
                    "id": survey.id,
                    "lat": float(survey.latitude),
                    "lng": float(survey.longitude),
                    "label": str(survey),
                    "result": result_code,
                    "result_label": result_code.replace("_", " ").title() if result_code else "",
                    "voters": survey.voters_count,
                    "color": RESULT_COLORS.get(result_code, DEFAULT_VISIT_COLOR),
                    "type_icon": "geolocation",
                    "url": fieldsurvey_detail_url(survey.pk),
                }
            )

        competitor_data = []
        for ad in competitor_ads:
            competitor_data.append(
                {
                    "id": ad.id,
                    "lat": float(ad.latitude),
                    "lng": float(ad.longitude),
                    "label": str(ad.competitor),
                    "type_label": ad.advertising_type.name if ad.advertising_type_id else "",
                    "type_icon": ad.advertising_type.icon
                    if ad.advertising_type_id
                    else "element-12",
                    "color": ad.competitor.color or "#d9214e",
                    "url": competitor_detection_detail_url(ad.id),
                }
            )

        return JsonResponse({"visits": visits, "competitor_ads": competitor_data})


def build_result_distribution(result_counts):
    """Build the donut input: ordered list of {code, label, value, color}."""
    rows = [
        ("APOYA", "Apoyan", result_counts.get("support") or 0),
        ("INDECISO", "Indecisos", result_counts.get("undecided") or 0),
        ("NO_APOYA", "No apoyan", result_counts.get("not_support") or 0),
        ("ATENDIO", "Atendieron", result_counts.get("attended") or 0),
        ("NO_ATENDIO", "No atendieron", result_counts.get("not_attended") or 0),
    ]
    return [
        {"code": code, "label": label, "value": value, "color": RESULT_COLORS[code]}
        for code, label, value in rows
    ]


def build_visits_trend(request, surveys):
    """Daily visit counts over the active range (or the last 30 days by default)."""
    today = timezone.localdate()
    date_from = request.GET.get("date_from") or None
    date_to = request.GET.get("date_to") or None
    try:
        start = (
            timezone.datetime.fromisoformat(date_from).date() if date_from else today - timedelta(days=29)
        )
        end = timezone.datetime.fromisoformat(date_to).date() if date_to else today
    except ValueError:
        start, end = today - timedelta(days=29), today
    if end < start:
        start, end = end, start

    counts = {
        row["day"]: row["count"]
        for row in surveys.annotate(day=TruncDate("created_date"))
        .values("day")
        .annotate(count=Count("id", distinct=True))
        .filter(day__gte=start, day__lte=end)
    }
    labels, values = [], []
    cursor = start
    while cursor <= end:
        labels.append(cursor.strftime("%d %b"))
        values.append(counts.get(cursor, 0))
        cursor += timedelta(days=1)
    return {"labels": labels, "values": values}


def build_competitor_breakdown(competitor_ads):
    """Top competitors by detection count for the small breakdown card."""
    rows = list(
        competitor_ads.values(
            "competitor_id",
            "competitor__political_organization",
            "competitor__color",
        )
        .annotate(detections=Count("id"))
        .order_by("-detections")[:5]
    )
    total = sum(row["detections"] for row in rows) or 1
    for row in rows:
        row["pct"] = int(round((row["detections"] / total) * 100))
        row["color"] = row["competitor__color"] or "#d9214e"
        row["label"] = row["competitor__political_organization"] or "—"
    return rows


def get_filter_context(request):
    campaigns = Campaign.objects.filter(is_active=True).order_by("name")
    if not can_view_all_field_surveys(request.user):
        campaigns = campaigns.filter(field_surveys__brigadier=request.user).distinct()
    return {
        "filter_campaigns": campaigns,
        "filter_results": SurveyResultOption.objects.filter(is_active=True).order_by(
            "order", "name"
        ),
        "filter_brigadiers": FieldSurvey.objects.values(
            "brigadier_id", "brigadier__username", "brigadier__first_name", "brigadier__last_name"
        )
        .distinct()
        .order_by("brigadier__first_name", "brigadier__last_name", "brigadier__username"),
    }
