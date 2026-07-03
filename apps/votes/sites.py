from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import DropdownFilterMixin, OrderingMixin

from .forms import (
    ElectoralCandidateOptionForm,
    ElectoralDignityForm,
    ElectoralDistrictForm,
    ElectoralResultReportForm,
    ElectoralTableAssignmentForm,
    ElectoralTableForm,
    ElectoralVenueForm,
)


@register("votes.ElectoralDignity")
class ElectoralDignitySite(BaseSite):
    form_class = ElectoralDignityForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Dignidades electorales"
    list_fields = ("name", "get_scope_display:Ámbito", "get_parish_kind_rule_display:Parroquias", "seats", "order", "is_active:Activo")
    detail_fields = ElectoralDignityForm.Meta.fieldsets
    search_params = ("name__icontains",)
    filter_fields = ("scope:Ámbito", "parish_kind_rule:Tipo de parroquia", "is_active:Activo")


@register("votes.ElectoralDistrict")
class ElectoralDistrictSite(BaseSite):
    form_class = ElectoralDistrictForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Circunscripciones electorales"
    list_fields = ("dignity", "name", "get_kind_display:Tipo", "province", "canton", "seats", "is_active:Activo")
    detail_fields = ElectoralDistrictForm.Meta.fieldsets
    search_params = ("name__icontains", "dignity__name__icontains")
    filter_fields = ("dignity:Dignidad", "kind:Tipo", "province:Provincia", "canton:Cantón", "is_active:Activo")


@register("votes.ElectoralCandidateOption")
class ElectoralCandidateOptionSite(BaseSite):
    form_class = ElectoralCandidateOptionForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Candidaturas electorales"
    list_fields = ("district", "list_code", "candidate_name", "order", "is_active:Activo")
    detail_fields = ElectoralCandidateOptionForm.Meta.fieldsets
    search_params = ("list_code__icontains", "candidate_name__icontains", "district__name__icontains", "district__dignity__name__icontains")
    filter_fields = ("district:Circunscripción", "is_active:Activo")


@register("votes.ElectoralVenue")
class ElectoralVenueSite(BaseSite):
    form_class = ElectoralVenueForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Recintos electorales"
    list_fields = ("name", "parish", "latitude", "longitude", "is_active:Activo")
    detail_fields = {
        "Recinto electoral": (
            ("parish",),
            ("latitude", "longitude"),
            ("name", "is_active"),
        ),
    }
    search_params = ("name__icontains", "parish__name__icontains")
    filter_fields = ("parish:Parroquia", "is_active:Activo")
    detail_maps = (("Ubicación GPS", "latitude", "longitude"),)


@register("votes.ElectoralTable")
class ElectoralTableSite(BaseSite):
    form_class = ElectoralTableForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Mesas electorales"
    list_fields = ("venue", "number", "get_gender_display:Género", "registered_voters", "is_active:Activo")
    detail_fields = ElectoralTableForm.Meta.fieldsets
    search_params = ("number__icontains", "venue__name__icontains", "venue__parish__name__icontains")
    filter_fields = ("venue:Recinto", "gender:Género", "is_active:Activo")


@register("votes.ElectoralTableAssignment")
class ElectoralTableAssignmentSite(BaseSite):
    form_class = ElectoralTableAssignmentForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Asignaciones de mesas"
    list_fields = ("table", "watcher", "notes", "is_active:Activo")
    detail_fields = ElectoralTableAssignmentForm.Meta.fieldsets
    search_params = ("table__number__icontains", "table__venue__name__icontains", "watcher__username__icontains", "watcher__email__icontains")
    filter_fields = ("table:Mesa", "watcher:Veedor", "is_active:Activo")


@register("votes.ElectoralResultReport")
class ElectoralResultReportSite(BaseSite):
    form_class = ElectoralResultReportForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Actas de resultados"
    list_fields = ("parish", "venue", "table", "dignity", "district", "get_status_display:Estado", "voters_count", "evidence_file")
    detail_fields = ElectoralResultReportForm.Meta.fieldsets
    search_params = ("venue__name__icontains", "table__number__icontains", "dignity__name__icontains", "district__name__icontains")
    filter_fields = ("dignity:Dignidad", "district:Circunscripción", "status:Estado", "parish:Parroquia")
