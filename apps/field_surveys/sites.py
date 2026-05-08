"""Register field-survey models in superadmin."""

from superadmin.decorators import register

from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin
from core.form_mixins import SaveOptionsMixin
from core.list_mixins import DropdownFilterMixin
from core.map_mixins import MapAjaxCreateMixin, MapInitialLocationMixin

from .forms import (
    AdvertisingTypeForm,
    CompetitorAdvertisingDetectionForm,
    CompetitorForm,
    FieldSurveyForm,
    SurveyAdvertisingResponseForm,
    SurveySupportLevelForm,
)
from .views import can_view_all_field_surveys


class FieldSurveyMapInitialLocationMixin(MapInitialLocationMixin):
    """Prefill GPS coordinates when the create form is opened from the map."""

    coordinate_initial_fields = ("latitude", "longitude")


class FieldSurveyMapAjaxCreateMixin(MapAjaxCreateMixin):
    """Render and submit the create form inside the map modal."""

    map_form_template_name = "field_surveys/_map_create_form.html"
    map_detail_url_name = "site:field_surveys_fieldsurvey_"


class CompetitorDetectionMapAjaxCreateMixin(FieldSurveyMapAjaxCreateMixin):
    map_detail_url_name = "site:field_surveys_competitoradvertisingdetection_"


class FieldSurveyOwnershipMixin:
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


class CompetitorDetectionOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(brigadier=self.request.user)


@register("field_surveys.SurveySupportLevel")
class SurveySupportLevelSite(BaseSite):
    form_class = SurveySupportLevelForm
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "color", "order", "is_active:Activo")
    detail_fields = SurveySupportLevelForm.Meta.fieldsets
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.SurveyAdvertisingResponse")
class SurveyAdvertisingResponseSite(BaseSite):
    form_class = SurveyAdvertisingResponseForm
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "color", "order", "is_active:Activo")
    detail_fields = SurveyAdvertisingResponseForm.Meta.fieldsets
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
    list_fields = (
        "campaign",
        "list_number",
        "political_organization",
        "candidate_name",
        "is_active:Activo",
    )
    detail_fields = CompetitorForm.Meta.fieldsets
    search_params = (
        "list_number__icontains",
        "political_organization__icontains",
        "candidate_name__icontains",
    )
    filter_fields = ("campaign:Campaña", "is_active:Activo")


@register("field_surveys.FieldSurvey")
class FieldSurveySite(BaseSite):
    form_class = FieldSurveyForm
    list_template_name = "field_surveys/fieldsurvey_list.html"
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
    list_fields = (
        "campaign",
        "brigadier",
        "support_level",
        "advertising_response",
        "voters_count",
        "created_date:Fecha",
    )
    detail_fields = {
        "Campaña y ubicación": (
            ("campaign",),
            ("brigadier",),
            ("latitude", "longitude"),
            ("gps_accuracy", "location_was_manually_adjusted"),
        ),
        "Visita": (
            ("voters_count",),
            ("support_level", "advertising_response"),
            ("photo",),
            ("notes",),
        ),
    }
    search_params = ("campaign__name__icontains", "brigadier__username__icontains")
    filter_fields = (
        "campaign:Campaña",
        "brigadier:Brigadista",
        "support_level:Nivel de apoyo",
        "advertising_response:Publicidad",
        "created_date:Fecha",
    )
    detail_maps = (("Ubicación GPS", "latitude", "longitude"),)


@register("field_surveys.CompetitorAdvertisingDetection")
class CompetitorAdvertisingDetectionSite(BaseSite):
    form_class = CompetitorAdvertisingDetectionForm
    list_template_name = "field_surveys/competitordetection_list.html"
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
        ),
        "Evidencia": (
            ("photo",),
            ("observation",),
        ),
    }
    search_params = (
        "competitor__political_organization__icontains",
        "competitor__candidate_name__icontains",
        "observation__icontains",
    )
    filter_fields = (
        "campaign:Campaña",
        "competitor:Competidor",
        "brigadier:Brigadista",
        "advertising_type:Tipo",
        "created_date:Fecha",
    )
    detail_maps = (("Ubicación GPS", "latitude", "longitude"),)
