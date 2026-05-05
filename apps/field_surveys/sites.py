from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import DropdownFilterMixin

from .forms import (
    CompetitorAdvertisingDetectionForm,
    CompetitorForm,
    FieldSurveyForm,
    SurveyResultOptionForm,
)
from .models import (
    Competitor,
    CompetitorAdvertisingDetection,
    CompetitorAdvertisingType,
    FieldSurvey,
    OwnAdvertisingType,
    OwnAdvertisingPlacement,
    SurveyResultOption,
)
from .views import can_view_all_field_surveys


class FieldSurveyOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(brigadier=self.request.user)


class OwnAdvertisingOwnershipMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        if can_view_all_field_surveys(self.request.user):
            return queryset
        return queryset.filter(field_survey__brigadier=self.request.user)


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
    detail_fields = (("code", "name"), ("order", "is_active"))
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.OwnAdvertisingType")
class OwnAdvertisingTypeSite(BaseSite):
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "order", "is_active:Activo")
    detail_fields = (("code", "name"), ("order", "is_active"))
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.CompetitorAdvertisingType")
class CompetitorAdvertisingTypeSite(BaseSite):
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("code", "name", "order", "is_active:Activo")
    detail_fields = (("code", "name"), ("order", "is_active"))
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("field_surveys.Competitor")
class CompetitorSite(BaseSite):
    form_class = CompetitorForm
    list_mixins = (DropdownFilterMixin,)
    list_fields = ("campaign", "list_number", "political_organization", "candidate_name", "is_active:Activo")
    detail_fields = {
        "Competidor": (
            ("campaign", "list_number"),
            ("political_organization", "candidate_name"),
            ("color", "is_active"),
            ("notes",),
        ),
    }
    search_params = ("list_number__icontains", "political_organization__icontains", "candidate_name__icontains")
    filter_fields = ("campaign:Campaña", "is_active:Activo")


@register("field_surveys.FieldSurvey")
class FieldSurveySite(BaseSite):
    form_class = FieldSurveyForm
    list_template_name = "field_surveys/superadmin_fieldsurvey_list.html"
    list_mixins = (FieldSurveyOwnershipMixin, DropdownFilterMixin)
    detail_mixins = (FieldSurveyOwnershipMixin,)
    update_mixins = (FieldSurveyOwnershipMixin,)
    delete_mixins = (FieldSurveyOwnershipMixin,)
    list_fields = ("campaign", "brigadier", "parish", "neighborhood", "voters_count", "created_date:Fecha")
    detail_fields = {
        "Campaña y ubicación": (
            ("campaign", "brigadier"),
            ("latitude", "longitude"),
            ("gps_accuracy", "location_was_manually_adjusted"),
        ),
        "Territorio": (
            ("parish", "neighborhood"),
            ("address",),
            ("reference",),
        ),
        "Persona o vivienda": (
            ("person_name", "person_phone"),
            ("voters_count",),
            ("results",),
            ("notes",),
        ),
        "Auditoría": (
            ("created_by", "created_date"),
            ("modified_date",),
        ),
    }
    search_params = ("person_name__icontains", "person_phone__icontains", "address__icontains", "reference__icontains")
    filter_fields = ("campaign:Campaña", "brigadier:Brigadista", "parish:Parroquia", "neighborhood:Barrio", "results:Resultado", "created_date:Fecha")


@register("field_surveys.OwnAdvertisingPlacement")
class OwnAdvertisingPlacementSite(BaseSite):
    list_mixins = (OwnAdvertisingOwnershipMixin, DropdownFilterMixin)
    detail_mixins = (OwnAdvertisingOwnershipMixin,)
    update_mixins = (OwnAdvertisingOwnershipMixin,)
    delete_mixins = (OwnAdvertisingOwnershipMixin,)
    list_fields = ("field_survey", "advertising_type", "created_by", "created_date:Fecha")
    detail_fields = {
        "Publicidad": (
            ("field_survey", "advertising_type"),
            ("photo",),
            ("latitude", "longitude"),
            ("observation",),
            ("created_by", "created_date"),
        )
    }
    search_params = ("observation__icontains",)
    filter_fields = ("advertising_type:Tipo", "created_date:Fecha")


@register("field_surveys.CompetitorAdvertisingDetection")
class CompetitorAdvertisingDetectionSite(BaseSite):
    form_class = CompetitorAdvertisingDetectionForm
    list_mixins = (CompetitorDetectionOwnershipMixin, DropdownFilterMixin)
    detail_mixins = (CompetitorDetectionOwnershipMixin,)
    update_mixins = (CompetitorDetectionOwnershipMixin,)
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
            ("created_by", "created_date"),
        ),
    }
    search_params = ("address__icontains", "reference__icontains", "observation__icontains")
    filter_fields = ("campaign:Campaña", "competitor:Competidor", "brigadier:Brigadista", "advertising_type:Tipo", "created_date:Fecha")
