from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import DropdownFilterMixin, OrderingMixin

from .forms import SurveyForm


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
