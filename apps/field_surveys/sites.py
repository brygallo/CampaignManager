"""Register field-survey models in superadmin."""
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse

from superadmin.decorators import register

from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin
from core.form_mixins import SaveOptionsMixin
from core.list_mixins import DropdownFilterMixin

from .forms import (
    AdvertisingTypeForm,
    CompetitorAdvertisingDetectionForm,
    CompetitorForm,
    FieldSurveyForm,
    SurveyResultOptionForm,
)
from .models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyResultOption,
)
from .views import can_view_all_field_surveys


class FieldSurveyMapInitialLocationMixin:
    """Prefill GPS coordinates when the create form is opened from the map."""

    coordinate_initial_fields = ("latitude", "longitude")
    allowed_map_layers = {"carto", "osm", "satellite"}

    def get_initial(self):
        initial = super().get_initial()
        for field in self.coordinate_initial_fields:
            value = self.request.GET.get(field)
            if value:
                initial[field] = value
        return initial

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        field = form.fields.get("location")
        if not field:
            return form

        zoom = self.request.GET.get("map_zoom")
        if zoom:
            try:
                parsed_zoom = int(float(zoom))
            except (TypeError, ValueError):
                parsed_zoom = None
            if parsed_zoom is not None:
                field.widget.attrs["data-default-zoom"] = max(1, min(parsed_zoom, 20))

        layer = self.request.GET.get("map_layer")
        if layer in self.allowed_map_layers:
            field.widget.attrs["data-default-basemap"] = layer

        return form


class FieldSurveyMapAjaxCreateMixin:
    """Render and submit the create form inside the map modal."""

    # Subclasses set this to the URL name of the detail view of the model
    # they create, so the AJAX response can carry the new record's link.
    map_detail_url_name = "site:field_surveys_fieldsurvey_"

    def _is_map_ajax(self):
        return self.request.headers.get("X-Map-Create") == "1"

    def _render_map_form(self, form):
        return render_to_string(
            "field_surveys/_map_create_form.html",
            {"form": form, "action_url": self.request.get_full_path()},
            request=self.request,
        )

    def get(self, request, *args, **kwargs):
        if self._is_map_ajax():
            form = self.get_form()
            return JsonResponse({"html": self._render_map_form(form)})
        return super().get(request, *args, **kwargs)

    def form_invalid(self, form):
        if self._is_map_ajax():
            return JsonResponse(
                {"ok": False, "html": self._render_map_form(form)},
                status=400,
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self._is_map_ajax():
            return JsonResponse(
                {
                    "ok": True,
                    "id": self.object.pk,
                    "label": getattr(self.object, "code", None) or str(self.object),
                    "url": reverse(
                        self.map_detail_url_name,
                        kwargs={"pk": self.object.pk},
                    ),
                }
            )
        return response


class CompetitorDetectionMapAjaxCreateMixin(FieldSurveyMapAjaxCreateMixin):
    map_detail_url_name = "site:field_surveys_competitoradvertisingdetection_"


class FieldSurveyOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(brigadier=self.request.user)


class BrigadierAutoAssignMixin:
    """Stamp request.user as brigadier when the form does not collect it."""

    def form_valid(self, form):
        if not form.instance.brigadier_id:
            form.instance.brigadier = self.request.user
        return super().form_valid(form)


class CompetitorDetectionOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(brigadier=self.request.user)


@register("field_surveys.SurveyResultOption")
class SurveyResultOptionSite(BaseSite):
    form_class = SurveyResultOptionForm
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "order", "is_active:Activo")
    detail_fields = SurveyResultOptionForm.Meta.fieldsets
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.AdvertisingType")
class AdvertisingTypeSite(BaseSite):
    form_class = AdvertisingTypeForm
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "icon", "order", "is_active:Activo")
    detail_fields = AdvertisingTypeForm.Meta.fieldsets
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.Competitor")
class CompetitorSite(BaseSite):
    form_class = CompetitorForm
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("campaign", "list_number", "political_organization", "candidate_name", "is_active:Activo")
    detail_fields = CompetitorForm.Meta.fieldsets
    search_params = ("list_number__icontains", "political_organization__icontains", "candidate_name__icontains")
    filter_fields = ("campaign:Campaña", "is_active:Activo")


@register("field_surveys.FieldSurvey")
class FieldSurveySite(BaseSite):
    form_class = FieldSurveyForm
    list_template_name = "field_surveys/superadmin_fieldsurvey_list.html"
    list_mixins = (FieldSurveyOwnershipMixin, DropdownFilterMixin)
    create_mixins = (
        FieldSurveyMapInitialLocationMixin,
        FieldSurveyMapAjaxCreateMixin,
        BrigadierAutoAssignMixin,
        SaveOptionsMixin,
    )
    detail_mixins = (FieldSurveyOwnershipMixin, HideEmptyFieldsetsMixin, DetailMapsMixin)
    update_mixins = (FieldSurveyOwnershipMixin, BrigadierAutoAssignMixin)
    delete_mixins = (FieldSurveyOwnershipMixin,)

    always_visible_fieldsets = (
        "Campaña y ubicación",
        "Visita",
    )
    list_fields = ("code", "campaign", "brigadier", "voters_count", "created_date:Fecha")
    detail_fields = {
        "Campaña y ubicación": (
            ("code", "campaign"),
            ("brigadier",),
            ("latitude", "longitude"),
            ("gps_accuracy", "location_was_manually_adjusted"),
        ),
        "Visita": (
            ("voters_count",),
            ("results_display:Resultados",),
            ("notes",),
        ),
    }
    search_params = ("code__icontains",)
    filter_fields = ("campaign:Campaña", "brigadier:Brigadista", "results:Resultado", "created_date:Fecha")
    detail_maps = (("Ubicación GPS", "latitude", "longitude"),)


@register("field_surveys.CompetitorAdvertisingDetection")
class CompetitorAdvertisingDetectionSite(BaseSite):
    form_class = CompetitorAdvertisingDetectionForm
    list_template_name = "field_surveys/superadmin_competitordetection_list.html"
    list_mixins = (CompetitorDetectionOwnershipMixin, DropdownFilterMixin)
    create_mixins = (
        FieldSurveyMapInitialLocationMixin,
        CompetitorDetectionMapAjaxCreateMixin,
        BrigadierAutoAssignMixin,
        SaveOptionsMixin,
    )
    detail_mixins = (CompetitorDetectionOwnershipMixin, DetailMapsMixin)
    update_mixins = (CompetitorDetectionOwnershipMixin, BrigadierAutoAssignMixin)
    delete_mixins = (CompetitorDetectionOwnershipMixin,)
    list_fields = ("campaign", "competitor", "brigadier", "advertising_type", "created_date:Fecha")
    detail_fields = {
        "Competencia": (
            ("campaign", "competitor"),
            ("brigadier", "advertising_type"),
        ),
        "Ubicación": (
            ("latitude", "longitude"),
            ("gps_accuracy", "location_was_manually_adjusted"),
            ("address",),
            ("reference",),
        ),
        "Evidencia": (
            ("photo",),
            ("observation",),
        ),
    }
    search_params = ("address__icontains", "reference__icontains", "observation__icontains")
    filter_fields = ("campaign:Campaña", "competitor:Competidor", "brigadier:Brigadista", "advertising_type:Tipo", "created_date:Fecha")
    detail_maps = (("Ubicación GPS", "latitude", "longitude"),)
