from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.campaigns.models import Campaign

from .forms import FieldSurveyQuickForm
from .models import (
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    OwnAdvertisingPlacement,
    SurveyResultOption,
)


def can_view_all_field_surveys(user):
    return (
        user.is_superuser
        or user.is_staff
        or user.has_perm("field_surveys.view_all_fieldsurvey")
    )


def fieldsurvey_queryset_for_user(user):
    queryset = (
        FieldSurvey.objects.select_related("campaign", "brigadier", "created_by")
        .prefetch_related("results", "own_advertising_placements", "competitor_advertising_detections")
        .all()
    )
    if not can_view_all_field_surveys(user):
        queryset = queryset.filter(brigadier=user)
    return queryset


def fieldsurvey_list_url():
    return reverse("site:field_surveys_fieldsurvey_listar")


def fieldsurvey_detail_url(pk):
    return reverse("site:field_surveys_fieldsurvey_", kwargs={"pk": pk})


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
        if params.get("parish"):
            queryset = queryset.filter(parish__name__icontains=params["parish"])
        if params.get("neighborhood"):
            queryset = queryset.filter(neighborhood__name__icontains=params["neighborhood"])
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


class FieldSurveyQuickCreateView(LoginRequiredMixin, FormView):
    template_name = "field_surveys/survey_form.html"
    form_class = FieldSurveyQuickForm

    def form_valid(self, form):
        survey = form.save(commit=False)
        survey.brigadier = self.request.user
        survey.created_by = self.request.user
        survey.save()
        form.save_m2m()
        form.save_related_records(survey, self.request.user)
        messages.success(self.request, "Levantamiento guardado correctamente.")
        return redirect(fieldsurvey_detail_url(survey.pk))


class FieldSurveyDashboardView(FieldSurveyAccessMixin, FieldSurveyFilterMixin, TemplateView):
    template_name = "field_surveys/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        surveys = self.filtered_queryset()
        own_ads = OwnAdvertisingPlacement.objects.filter(field_survey__in=surveys)
        competitor_ads = CompetitorAdvertisingDetection.objects.filter(field_survey__in=surveys)
        if not can_view_all_field_surveys(self.request.user):
            competitor_ads = competitor_ads.filter(brigadier=self.request.user)

        context.update(get_filter_context(self.request))
        context["can_view_all"] = can_view_all_field_surveys(self.request.user)
        context["metrics"] = {
            "total_visits": surveys.count(),
            "total_voters": surveys.aggregate(total=Sum("voters_count"))["total"] or 0,
            "support": surveys.filter(results__code="APOYA").distinct().count(),
            "undecided": surveys.filter(results__code="INDECISO").distinct().count(),
            "not_support": surveys.filter(results__code="NO_APOYA").distinct().count(),
            "own_ads": own_ads.count(),
            "competitor_ads": competitor_ads.count(),
        }
        context["brigadier_ranking"] = (
            surveys.values("brigadier__first_name", "brigadier__last_name", "brigadier__username")
            .annotate(visits=Count("id"), voters=Sum("voters_count"))
            .order_by("-visits", "-voters")[:10]
        )
        return context


class FieldSurveyMapView(LoginRequiredMixin, TemplateView):
    template_name = "field_surveys/map.html"

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
        surveys = self.filtered_queryset()
        competitor_ads = CompetitorAdvertisingDetection.objects.select_related(
            "competitor", "campaign", "brigadier", "advertising_type"
        )
        if not can_view_all_field_surveys(request.user):
            competitor_ads = competitor_ads.filter(brigadier=request.user)
        if request.GET.get("campaign"):
            competitor_ads = competitor_ads.filter(campaign_id=request.GET["campaign"])
        if request.GET.get("competitor"):
            competitor_ads = competitor_ads.filter(competitor_id=request.GET["competitor"])

        data = {
            "visits": [
                {
                    "id": survey.id,
                    "lat": float(survey.latitude),
                    "lng": float(survey.longitude),
                    "result": survey.primary_result_code,
                    "voters": survey.voters_count,
                    "label": str(survey),
                    "url": fieldsurvey_detail_url(survey.pk),
                }
                for survey in surveys
            ],
            "own_ads": [
                {
                    "id": ad.id,
                    "lat": float(ad.latitude),
                    "lng": float(ad.longitude),
                    "type": str(ad.advertising_type),
                    "survey_id": ad.field_survey_id,
                }
                for ad in OwnAdvertisingPlacement.objects.select_related("advertising_type").filter(field_survey__in=surveys)
            ],
            "competitor_ads": [
                {
                    "id": ad.id,
                    "lat": float(ad.latitude),
                    "lng": float(ad.longitude),
                    "type": str(ad.advertising_type),
                    "competitor": str(ad.competitor),
                    "color": ad.competitor.color or "#d9214e",
                }
                for ad in competitor_ads
            ],
        }
        return JsonResponse(data)


def get_filter_context(request):
    campaigns = Campaign.objects.filter(is_active=True).order_by("name")
    if not can_view_all_field_surveys(request.user):
        campaigns = campaigns.filter(field_surveys__brigadier=request.user).distinct()
    return {
        "filter_campaigns": campaigns,
        "filter_results": SurveyResultOption.objects.filter(is_active=True).order_by("order", "name"),
        "filter_brigadiers": FieldSurvey.objects.values("brigadier_id", "brigadier__username", "brigadier__first_name", "brigadier__last_name")
        .distinct()
        .order_by("brigadier__first_name", "brigadier__last_name", "brigadier__username"),
    }
