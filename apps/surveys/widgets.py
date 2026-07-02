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
