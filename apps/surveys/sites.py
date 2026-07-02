from superadmin.decorators import register

from core.base import BaseSite
from core.form_policies import ConditionalPolicy, FieldPermissionPolicy
from core.list_mixins import DropdownFilterMixin, OrderingMixin

from .forms import SurveyForm


@register("surveys.Survey")
class SurveySite(BaseSite):
    form_class = SurveyForm
    form_policies = (
        FieldPermissionPolicy(
            fields=("status",),
            edit_permission="surveys.publish_survey",
            disabled_reason="Necesitas el permiso de publicación para cambiar el estado.",
        ),
        FieldPermissionPolicy(
            fields=("all_users_can_respond", "assigned_users"),
            edit_permission="surveys.manage_survey_assignments",
            disabled_reason="Necesitas el permiso de asignación para cambiar quién puede responder.",
        ),
        ConditionalPolicy(
            source="all_users_can_respond",
            operator="checked",
            targets=("assigned_users",),
            effects=("hide", "disable", "clear"),
        ),
    )
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
