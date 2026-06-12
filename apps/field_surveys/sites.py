"""Register field-survey models in superadmin."""

from superadmin.decorators import register

from core.audit import AuditContextMixin
from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin, ProtectedDeleteMixin
from core.form_mixins import SaveOptionsMixin
from core.list_mixins import DropdownFilterMixin, OrderingMixin
from core.map_mixins import MapAjaxDeleteMixin

from .forms import (
    AdvertisingTypeForm,
    CompetitorAdvertisingDetectionForm,
    CompetitorForm,
    FieldSurveyForm,
    SurveyAdvertisingResponseForm,
    SurveySupportLevelForm,
)
from .views import (
    BrigadierAutoAssignMixin,
    CompetitorDetectionMapAjaxCreateMixin,
    CompetitorDetectionMapAjaxUpdateMixin,
    CompetitorDetectionOwnershipMixin,
    FieldSurveyMapAjaxCreateMixin,
    FieldSurveyMapAjaxUpdateMixin,
    FieldSurveyMapInitialLocationMixin,
    FieldSurveyOwnershipMixin,
)


@register("field_surveys.SurveySupportLevel")
class SurveySupportLevelSite(BaseSite):
    form_class = SurveySupportLevelForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("code", "name", "color", "order", "is_active:Activo")
    detail_fields = SurveySupportLevelForm.Meta.fieldsets
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.SurveyAdvertisingResponse")
class SurveyAdvertisingResponseSite(BaseSite):
    form_class = SurveyAdvertisingResponseForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("code", "name", "color", "order", "is_active:Activo")
    detail_fields = SurveyAdvertisingResponseForm.Meta.fieldsets
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.AdvertisingType")
class AdvertisingTypeSite(BaseSite):
    form_class = AdvertisingTypeForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("code", "name", "icon", "order", "is_active:Activo")
    detail_fields = AdvertisingTypeForm.Meta.fieldsets
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.Competitor")
class CompetitorSite(BaseSite):
    form_class = CompetitorForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = (
        "campaign",
        "list_number",
        "acronym:Acrónimo",
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
    list_mixins = (FieldSurveyOwnershipMixin, OrderingMixin, DropdownFilterMixin)
    create_mixins = (
        FieldSurveyMapInitialLocationMixin,
        FieldSurveyMapAjaxCreateMixin,
        BrigadierAutoAssignMixin,
        SaveOptionsMixin,
    )
    detail_mixins = (FieldSurveyOwnershipMixin, AuditContextMixin, HideEmptyFieldsetsMixin, DetailMapsMixin)
    update_mixins = (
        FieldSurveyMapAjaxUpdateMixin,
        FieldSurveyOwnershipMixin,
        BrigadierAutoAssignMixin,
    )
    delete_mixins = (MapAjaxDeleteMixin, FieldSurveyOwnershipMixin, ProtectedDeleteMixin)

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
    search_params = (
        "campaign__name__icontains",
        "brigadier__username__icontains",
        "notes__icontains",
    )
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
    list_mixins = (CompetitorDetectionOwnershipMixin, OrderingMixin, DropdownFilterMixin)
    create_mixins = (
        FieldSurveyMapInitialLocationMixin,
        CompetitorDetectionMapAjaxCreateMixin,
        BrigadierAutoAssignMixin,
        SaveOptionsMixin,
    )
    detail_mixins = (CompetitorDetectionOwnershipMixin, AuditContextMixin, DetailMapsMixin)
    update_mixins = (
        CompetitorDetectionMapAjaxUpdateMixin,
        CompetitorDetectionOwnershipMixin,
        BrigadierAutoAssignMixin,
    )
    delete_mixins = (MapAjaxDeleteMixin, CompetitorDetectionOwnershipMixin, ProtectedDeleteMixin)
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
