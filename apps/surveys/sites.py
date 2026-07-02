from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import DropdownFilterMixin, OrderingMixin

from .forms import (
    ElectoralCandidateOptionForm,
    ElectoralDignityForm,
    ElectoralDistrictForm,
    ElectoralTableAssignmentForm,
    ElectoralTableForm,
    ElectoralVenueForm,
    SurveyForm,
    SurveyOptionForm,
    SurveyQuestionForm,
    SurveySectionForm,
)


@register("surveys.Survey")
class SurveySite(BaseSite):
    form_class = SurveyForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_template_name = "surveys/survey_list.html"
    detail_template_name = "surveys/survey_detail.html"
    respect_active_campaign = False
    list_fields = (
        "title",
        "get_status_display:Estado",
        "requires_login",
        "allow_multiple_responses",
        "created_by",
        "created_date",
    )
    detail_fields = SurveyForm.Meta.fieldsets
    search_params = ("title__icontains", "description__icontains", "slug__icontains")
    filter_fields = ("status:Estado", "requires_login:Login", "created_date:Creación")


@register("surveys.SurveySection")
class SurveySectionSite(BaseSite):
    form_class = SurveySectionForm
    respect_active_campaign = False
    list_fields = ("survey", "title", "order", "is_active:Activo")
    detail_fields = SurveySectionForm.Meta.fieldsets
    search_params = ("title__icontains", "survey__title__icontains")
    filter_fields = ("survey:Encuesta", "is_active:Activo")


@register("surveys.SurveyQuestion")
class SurveyQuestionSite(BaseSite):
    form_class = SurveyQuestionForm
    respect_active_campaign = False
    list_fields = ("survey", "section", "text", "get_question_type_display:Tipo", "order", "is_active:Activo")
    detail_fields = SurveyQuestionForm.Meta.fieldsets
    search_params = ("text__icontains", "survey__title__icontains")
    filter_fields = ("survey:Encuesta", "question_type:Tipo", "is_required:Obligatoria", "is_active:Activo")


@register("surveys.SurveyOption")
class SurveyOptionSite(BaseSite):
    form_class = SurveyOptionForm
    respect_active_campaign = False
    list_fields = ("question", "label", "value", "order", "is_active:Activo")
    detail_fields = SurveyOptionForm.Meta.fieldsets
    search_params = ("label__icontains", "value__icontains", "question__text__icontains")
    filter_fields = ("question:Pregunta", "is_active:Activo")


@register("surveys.ElectoralDignity")
class ElectoralDignitySite(BaseSite):
    form_class = ElectoralDignityForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Dignidades electorales"
    list_fields = (
        "name",
        "get_scope_display:Ámbito",
        "get_parish_kind_rule_display:Parroquias",
        "seats",
        "order",
        "is_active:Activo",
    )
    detail_fields = ElectoralDignityForm.Meta.fieldsets
    search_params = ("name__icontains",)
    filter_fields = ("scope:Ámbito", "parish_kind_rule:Tipo de parroquia", "is_active:Activo")


@register("surveys.ElectoralDistrict")
class ElectoralDistrictSite(BaseSite):
    form_class = ElectoralDistrictForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Circunscripciones electorales"
    list_fields = (
        "dignity",
        "name",
        "get_kind_display:Tipo",
        "province",
        "canton",
        "seats",
        "is_active:Activo",
    )
    detail_fields = ElectoralDistrictForm.Meta.fieldsets
    search_params = ("name__icontains", "dignity__name__icontains")
    filter_fields = ("dignity:Dignidad", "kind:Tipo", "province:Provincia", "canton:Cantón", "is_active:Activo")


@register("surveys.ElectoralCandidateOption")
class ElectoralCandidateOptionSite(BaseSite):
    form_class = ElectoralCandidateOptionForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Candidaturas electorales"
    list_fields = ("district", "list_code", "candidate_name", "order", "is_active:Activo")
    detail_fields = ElectoralCandidateOptionForm.Meta.fieldsets
    search_params = (
        "list_code__icontains",
        "candidate_name__icontains",
        "district__name__icontains",
        "district__dignity__name__icontains",
    )
    filter_fields = ("district:Circunscripción", "is_active:Activo")


@register("surveys.ElectoralVenue")
class ElectoralVenueSite(BaseSite):
    form_class = ElectoralVenueForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Recintos electorales"
    list_fields = ("name", "parish", "is_active:Activo")
    detail_fields = ElectoralVenueForm.Meta.fieldsets
    search_params = ("name__icontains", "parish__name__icontains")
    filter_fields = ("parish:Parroquia", "is_active:Activo")


@register("surveys.ElectoralTable")
class ElectoralTableSite(BaseSite):
    form_class = ElectoralTableForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Mesas electorales"
    list_fields = ("venue", "number", "get_gender_display:Género", "is_active:Activo")
    detail_fields = ElectoralTableForm.Meta.fieldsets
    search_params = ("number__icontains", "venue__name__icontains", "venue__parish__name__icontains")
    filter_fields = ("venue:Recinto", "gender:Género", "is_active:Activo")


@register("surveys.ElectoralTableAssignment")
class ElectoralTableAssignmentSite(BaseSite):
    form_class = ElectoralTableAssignmentForm
    respect_active_campaign = False
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    title = "Asignaciones de mesas"
    list_fields = ("table", "watcher", "notes", "is_active:Activo")
    detail_fields = ElectoralTableAssignmentForm.Meta.fieldsets
    search_params = (
        "table__number__icontains",
        "table__venue__name__icontains",
        "watcher__username__icontains",
        "watcher__email__icontains",
    )
    filter_fields = ("table:Mesa", "watcher:Veedor", "is_active:Activo")
