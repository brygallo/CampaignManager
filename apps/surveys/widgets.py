import json

from django import forms


class SurveyChoiceRadioSelect(forms.RadioSelect):
    template_name = "surveys/widgets/choice_cards.html"
    option_template_name = "surveys/widgets/choice_card_option.html"


class SurveyChoiceCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = "surveys/widgets/choice_cards.html"
    option_template_name = "surveys/widgets/choice_card_option.html"


class SurveyScaleRadioSelect(forms.RadioSelect):
    template_name = "surveys/widgets/scale_choices.html"
    option_template_name = "surveys/widgets/scale_choice_option.html"


class SurveyRankingWidget(forms.Widget):
    """Up/down reorderable list backed by a single hidden input.

    The hidden input carries the currently ordered option VALUES as a JSON
    array (kept in sync client-side by ``respond.html``'s ranking script).
    Rendered outside of any real HTML form control validation — the field
    is always built with ``required=False`` (see
    ``DynamicSurveyResponseForm.build_field``) and the full-permutation /
    required checks run server-side in ``DynamicSurveyResponseForm.clean``,
    the same pattern used by the LOCATION map widget for its lat/lng pair.
    """

    template_name = "surveys/widgets/ranking_list.html"

    def __init__(self, options=(), attrs=None):
        super().__init__(attrs)
        self.options = list(options)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["ordered_options"] = self._ordered_options(value)
        return context

    def _ordered_options(self, value):
        label_by_value = dict(self.options)
        try:
            submitted_values = json.loads(value) if value else []
        except (TypeError, ValueError):
            submitted_values = []
        if submitted_values and set(submitted_values) == set(label_by_value):
            return [(item, label_by_value[item]) for item in submitted_values]
        return list(self.options)

    def value_from_datadict(self, data, files, name):
        return data.get(name)

    def use_required_attribute(self, initial):
        return False
