from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from superadmin.shortcuts import get_urls_of_site
from superadmin.sites import site as superadmin_site

from core.map_mixins import (
    MapAjaxCreateMixin,
    MapAjaxUpdateMixin,
    MapInitialLocationMixin,
)

from .constants import (
    COMPETITOR_FALLBACK_COLOR,
    DEFAULT_VISIT_COLOR,
    MAX_MAP_POINTS,
)
from .models import (
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveySupportLevel,
)
from .services import (
    build_advertising_distribution,
    build_competitor_breakdown,
    build_support_distribution,
    build_visits_trend,
    get_filter_context,
)
from .utils import (
    advertising_color,
    can_view_all_field_surveys,
    competitor_detection_detail_url,
    fieldsurvey_detail_url,
    fieldsurvey_list_url,
    fieldsurvey_queryset_for_user,
    support_color,
)

# Names re-exported here keep ``from apps.field_surveys.views import ...``
# working for callers (sites.py, tests) after the helpers/builders moved to
# constants.py / utils.py / services.py.
__all__ = [
    "DEFAULT_VISIT_COLOR",
    "advertising_color",
    "build_advertising_distribution",
    "build_competitor_breakdown",
    "build_support_distribution",
    "build_visits_trend",
    "can_view_all_field_surveys",
    "competitor_detection_detail_url",
    "fieldsurvey_detail_url",
    "fieldsurvey_list_url",
    "fieldsurvey_queryset_for_user",
    "get_filter_context",
    "support_color",
]


class FieldSurveyMapInitialLocationMixin(MapInitialLocationMixin):
    """Prefill GPS coordinates when the create form is opened from the map."""

    coordinate_initial_fields = ("latitude", "longitude")


class FieldSurveyMapAjaxCreateMixin(MapAjaxCreateMixin):
    """Render and submit the create form inside the map modal."""

    map_form_template_name = "field_surveys/_map_create_form.html"
    map_detail_url_name = "site:field_surveys_fieldsurvey_"


class FieldSurveyMapAjaxUpdateMixin(MapAjaxUpdateMixin):
    """Render and submit the update form inside the map modal."""

    map_form_template_name = "field_surveys/_map_create_form.html"


class CompetitorDetectionMapAjaxCreateMixin(FieldSurveyMapAjaxCreateMixin):
    map_detail_url_name = "site:field_surveys_competitoradvertisingdetection_"


class CompetitorDetectionMapAjaxUpdateMixin(FieldSurveyMapAjaxUpdateMixin):
    pass


class FieldSurveyOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(brigadier=self.request.user)


class CompetitorDetectionOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(brigadier=self.request.user)


class BrigadierAutoAssignMixin:
    """Stamp request.user fields that are intentionally absent from map forms."""

    def form_valid(self, form):
        if not form.instance.brigadier_id:
            form.instance.brigadier = self.request.user
        if hasattr(form.instance, "created_by_id") and not form.instance.created_by_id:
            form.instance.created_by = self.request.user
        return super().form_valid(form)


class FieldSurveySpecialViewMixin(LoginRequiredMixin):
    def get_queryset(self):
        return fieldsurvey_queryset_for_user(self.request.user)


class FieldSurveyFilterMixin:
    def apply_filters(self, queryset):
        params = self.request.GET
        # Active-campaign fallback: explicit ``?campaign=`` in the URL wins
        # (deep links / charts keep working), otherwise the navbar's active
        # campaign is applied so dashboard KPIs match the rest of the UI.
        campaign_id = params.get("campaign")
        if not campaign_id and getattr(self.request, "active_campaign", None):
            campaign_id = str(self.request.active_campaign.pk)
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        if params.get("brigadier") and can_view_all_field_surveys(self.request.user):
            queryset = queryset.filter(brigadier_id=params["brigadier"])
        if params.get("support_level"):
            queryset = queryset.filter(support_level_id=params["support_level"])
        if params.get("advertising_response"):
            queryset = queryset.filter(advertising_response_id=params["advertising_response"])
        if params.get("date_from"):
            queryset = queryset.filter(created_date__date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(created_date__date__lte=params["date_to"])
        return queryset

    def filtered_queryset(self):
        return self.apply_filters(self.get_queryset())


class FieldSurveyAccessMixin(FieldSurveySpecialViewMixin):
    pass


class FieldSurveyDashboardView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, TemplateView):
    template_name = "field_surveys/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Dashboard de levantamientos"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Levantamientos de campo", None),
            ("Dashboard", None),
        ]
        surveys = self.filtered_queryset()
        competitor_ads = CompetitorAdvertisingDetection.objects.filter(field_survey__in=surveys)
        if not can_view_all_field_surveys(self.request.user):
            competitor_ads = competitor_ads.filter(brigadier=self.request.user)

        context.update(get_filter_context(self.request))
        context["can_view_all"] = can_view_all_field_surveys(self.request.user)
        result_counts = surveys.aggregate(
            total_visits=Count("id", distinct=True),
            total_voters=Sum("voters_count"),
            support=Count("id", filter=Q(support_level__code="APOYA"), distinct=True),
            undecided=Count("id", filter=Q(support_level__code="INDECISO"), distinct=True),
            not_support=Count("id", filter=Q(support_level__code="NO_APOYA"), distinct=True),
            not_attended=Count("id", filter=Q(support_level__code="NO_ATENDIO"), distinct=True),
            ads_accepted=Count(
                "id", filter=Q(advertising_response__code="ACEPTA"), distinct=True
            ),
            ads_rejected=Count(
                "id", filter=Q(advertising_response__code="RECHAZA"), distinct=True
            ),
        )
        context["metrics"] = {
            "total_visits": result_counts["total_visits"] or 0,
            "total_voters": result_counts["total_voters"] or 0,
            "support": result_counts["support"] or 0,
            "undecided": result_counts["undecided"] or 0,
            "not_support": result_counts["not_support"] or 0,
            "not_attended": result_counts["not_attended"] or 0,
            "ads_accepted": result_counts["ads_accepted"] or 0,
            "ads_rejected": result_counts["ads_rejected"] or 0,
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

        result_distribution = build_support_distribution(result_counts)
        advertising_distribution = build_advertising_distribution(result_counts)
        context["result_distribution"] = result_distribution
        context["advertising_distribution"] = advertising_distribution

        visits_trend = build_visits_trend(self.request, surveys)
        competitor_ads_breakdown = build_competitor_breakdown(competitor_ads)
        context["competitor_ads_breakdown"] = competitor_ads_breakdown

        context["chart_data"] = {
            "results": [
                {"label": item["label"], "value": item["value"], "color": item["color"]}
                for item in result_distribution
            ],
            "advertising": [
                {"label": item["label"], "value": item["value"], "color": item["color"]}
                for item in advertising_distribution
            ],
            "trend": visits_trend,
        }
        return context


class FieldSurveyDashboardHeatmapDataView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, View):
    """Return density points for the dashboard heatmap, grouped by layer.

    Honors the dashboard filters via FieldSurveyFilterMixin and returns layers
    for support levels (APOYA, INDECISO) plus competitor advertising detections.
    Each layer is a list of [lat, lng, weight] tuples plus a count.
    """

    def _survey_points(self, base_qs, support_code):
        rows = (
            base_qs.filter(support_level__code=support_code)
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

        support_levels_by_code = {
            level.code: level
            for level in SurveySupportLevel.objects.filter(is_active=True)
        }
        layers = {
            "apoyo": {
                "label": "Apoyo",
                "color": support_color(support_levels_by_code.get("APOYA")),
                "points": self._survey_points(surveys, "APOYA"),
            },
            "indecisos": {
                "label": "Indecisos",
                "color": support_color(support_levels_by_code.get("INDECISO")),
                "points": self._survey_points(surveys, "INDECISO"),
            },
            "competencia": {
                "label": "Competencia",
                "color": COMPETITOR_FALLBACK_COLOR,
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
        context["page_title"] = "Mapa de levantamientos"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Levantamientos de campo", None),
            ("Mapa", None),
        ]
        context.update(get_filter_context(self.request))
        context["can_view_all"] = can_view_all_field_surveys(self.request.user)
        competitors = Competitor.objects.filter(is_active=True)
        active_campaign_id = context.get("active_campaign_filter_id")
        if active_campaign_id:
            competitors = competitors.filter(campaign_id=active_campaign_id)
        context["competitors"] = competitors.order_by(
            "campaign__name", "list_number", "political_organization"
        )
        return context


class FieldSurveyMapDataView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, View):
    # Hard ceiling on points returned per response (see MAX_MAP_POINTS).
    MAX_POINTS = MAX_MAP_POINTS

    def get(self, request, *args, **kwargs):
        # Active-campaign fallback: explicit ``?campaign=`` in the URL wins,
        # otherwise the navbar's active campaign is applied. Visits use the
        # filter mixin (which already reads ``?campaign=`` from GET), so we
        # rewrite GET in place before the filter mixin sees it.
        if not request.GET.get("campaign") and getattr(request, "active_campaign", None):
            params = request.GET.copy()
            params["campaign"] = str(request.active_campaign.pk)
            request.GET = params

        surveys = self.filtered_queryset().select_related(
            "campaign", "brigadier", "support_level", "advertising_response"
        )
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

        # Count first (cheap aggregate) and slice before materialising in
        # Python. We split the budget proportionally between visits and
        # competitor ads so a tenant with mostly visits doesn't lose the
        # competitor layer entirely.
        survey_total = surveys.count()
        competitor_total = competitor_ads.count()
        grand_total = survey_total + competitor_total
        truncated = grand_total > self.MAX_POINTS
        if truncated:
            survey_cap = int(self.MAX_POINTS * survey_total / grand_total)
            competitor_cap = self.MAX_POINTS - survey_cap
            surveys = surveys.order_by("-created_date")[:survey_cap]
            competitor_ads = competitor_ads.order_by("-created_date")[:competitor_cap]

        # Same perm gating the list views use: ``get_urls_of_site`` only returns
        # update/delete keys when the user has the matching change_/delete_ perm.
        survey_site = superadmin_site.get_modelsite(FieldSurvey)
        competitor_site = superadmin_site.get_modelsite(CompetitorAdvertisingDetection)

        visits = []
        for survey in surveys:
            level = survey.support_level
            response = survey.advertising_response
            survey_urls = get_urls_of_site(survey_site, object=survey, user=request.user)
            item = {
                "id": survey.id,
                "kind": "visit",
                "lat": float(survey.latitude),
                "lng": float(survey.longitude),
                "label": str(survey),
                "support_code": level.code if level else "",
                "support_label": level.name if level else "",
                "advertising_code": response.code if response else "",
                "advertising_label": response.name if response else "",
                "voters": survey.voters_count,
                "color": support_color(level),
                "url": fieldsurvey_detail_url(survey.pk),
            }
            if "update" in survey_urls:
                item["update_url"] = survey_urls["update"]
            if "delete" in survey_urls:
                item["delete_url"] = survey_urls["delete"]
            visits.append(item)

        competitor_data = []
        for ad in competitor_ads:
            ad_urls = get_urls_of_site(competitor_site, object=ad, user=request.user)
            item = {
                "id": ad.id,
                "kind": "competitor",
                "lat": float(ad.latitude),
                "lng": float(ad.longitude),
                "label": str(ad.competitor),
                "type_label": ad.advertising_type.name if ad.advertising_type_id else "",
                "type_icon": ad.advertising_type.icon
                if ad.advertising_type_id
                else "element-12",
                "color": ad.competitor.color or COMPETITOR_FALLBACK_COLOR,
                "acronym": ad.competitor.marker_acronym,
                "url": competitor_detection_detail_url(ad.id),
            }
            if "update" in ad_urls:
                item["update_url"] = ad_urls["update"]
            if "delete" in ad_urls:
                item["delete_url"] = ad_urls["delete"]
            competitor_data.append(item)

        return JsonResponse(
            {
                "visits": visits,
                "competitor_ads": competitor_data,
                "truncated": truncated,
                "total": grand_total,
                "returned": len(visits) + len(competitor_data),
                "limit": self.MAX_POINTS,
            }
        )
