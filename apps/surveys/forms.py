from django import forms
from django.utils.text import slugify
from django_select2.forms import ModelSelect2MultipleWidget
from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget

from .models import (
    Survey,
    SurveyOption,
    SurveyQuestion,
    SurveySection,
)
from .widgets import (
    SurveyChoiceCheckboxSelectMultiple,
    SurveyChoiceRadioSelect,
    SurveyScaleRadioSelect,
)


class SurveyForm(ModelForm):
    class Meta:
        model = Survey
        fieldsets = {
            "Encuesta": (
                ("title", "slug"),
                ("description",),
                ("status",),
            ),
            "Disponibilidad": (
                ("starts_at", "ends_at"),
                ("requires_login", "allow_multiple_responses"),
                ("is_anonymous",),
            ),
            "Asignación": (
                ("all_users_can_respond",),
                ("assigned_users",),
            ),
            "Confirmación": (
                ("thank_you_message",),
            ),
        }
        widgets = {
            "assigned_users": ModelSelect2MultipleWidget(
                model="authentication.User",
                search_fields=[
                    "username__icontains",
                    "email__icontains",
                    "first_name__icontains",
                    "last_name__icontains",
                ],
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Usuarios que pueden responder",
                },
            ),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        title = self.cleaned_data.get("title")
        return slug or slugify(title or "")


class SurveyQuestionConditionSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            raw_value = getattr(value, "value", value)
            try:
                question = self.choices.queryset.get(pk=raw_value)
            except (AttributeError, SurveyQuestion.DoesNotExist, ValueError, TypeError):
                question = None
            if question is not None:
                option["attrs"]["data-question-type"] = question.question_type
        return option


class SurveyOptionConditionSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            raw_value = getattr(value, "value", value)
            try:
                survey_option = self.choices.queryset.get(pk=raw_value)
            except (AttributeError, SurveyOption.DoesNotExist, ValueError, TypeError):
                survey_option = None
            if survey_option is not None:
                option["attrs"]["data-question-id"] = str(survey_option.question_id)
        return option


class SurveyQuestionBuilderForm(forms.ModelForm):
    section = forms.ModelChoiceField(
        label="Sección",
        queryset=SurveySection.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    visibility_question = forms.ModelChoiceField(
        label="Mostrar según respuesta a",
        queryset=SurveyQuestion.objects.none(),
        required=False,
        widget=SurveyQuestionConditionSelect(
            attrs={
                "class": "form-select form-select-solid",
                "data-survey-builder-field": "visibility-question",
            }
        ),
    )
    visibility_option = forms.ModelChoiceField(
        label="Opción esperada",
        queryset=SurveyOption.objects.none(),
        required=False,
        widget=SurveyOptionConditionSelect(
            attrs={
                "class": "form-select form-select-solid",
                "data-survey-builder-field": "visibility-option",
            }
        ),
        help_text="Úsalo cuando la pregunta condicionante es de selección.",
    )
    option_lines = forms.MultipleChoiceField(
        label="Opciones",
        required=False,
        choices=(),
        widget=forms.SelectMultiple(
            attrs={
                "class": "django-select2 form-select form-select-solid",
                "data-tags": "true",
                "data-placeholder": "Agrega opciones",
                "data-survey-builder-field": "options",
            }
        ),
        help_text="Solo aplica para selección única o múltiple. Escribe una opción y presiona Enter.",
    )

    class Meta:
        model = SurveyQuestion
        fields = (
            "section",
            "text",
            "help_text",
            "question_type",
            "is_required",
            "visibility_question",
            "visibility_operator",
            "visibility_option",
            "visibility_value",
        )
        widgets = {
            "text": forms.TextInput(attrs={"class": "form-control form-control-solid"}),
            "help_text": forms.TextInput(attrs={"class": "form-control form-control-solid"}),
            "question_type": forms.Select(
                attrs={
                    "class": "form-select form-select-solid",
                    "data-survey-builder-field": "question-type",
                }
            ),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "visibility_operator": forms.Select(
                attrs={
                    "class": "form-select form-select-solid",
                    "data-survey-builder-field": "visibility-operator",
                }
            ),
            "visibility_value": forms.TextInput(
                attrs={
                    "class": "form-control form-control-solid",
                    "data-survey-builder-field": "visibility-value",
                }
            ),
        }

    def __init__(self, *args, survey=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        option_choices = []
        if self.instance and self.instance.pk and not self.is_bound:
            option_choices = list(
                self.instance.options.filter(is_active=True)
                .order_by("order")
                .values_list("label", "label")
            )
            self.fields["option_lines"].initial = [value for value, _label in option_choices]
        if survey is not None:
            survey_option_choices = list(
                SurveyOption.objects.filter(question__survey=survey, is_active=True)
                .order_by("label")
                .values_list("label", "label")
                .distinct()
            )
            option_choices = list(dict(option_choices + survey_option_choices).items())
            self.fields["section"].queryset = survey.sections.filter(is_active=True).order_by(
                "order", "title"
            )
            visibility_questions = survey.questions.filter(is_active=True)
            if self.instance and self.instance.pk:
                visibility_questions = visibility_questions.exclude(pk=self.instance.pk)
            self.fields["visibility_question"].queryset = visibility_questions.order_by(
                "section__order", "order", "id"
            )
            self.fields["visibility_option"].queryset = SurveyOption.objects.filter(
                question__survey=survey,
                is_active=True,
            ).order_by("question__order", "order", "label")
        if self.is_bound:
            if hasattr(self.data, "getlist"):
                submitted_options = self.data.getlist(self.add_prefix("option_lines"))
            else:
                submitted_options = self.data.get(self.add_prefix("option_lines"), [])
                if isinstance(submitted_options, str):
                    submitted_options = [submitted_options]
            option_choices = list(
                dict(option_choices + [(value, value) for value in submitted_options if str(value).strip()]).items()
            )
        self.fields["option_lines"].choices = option_choices

    def clean(self):
        cleaned_data = super().clean()
        qtype = cleaned_data.get("question_type")
        option_lines = cleaned_data.get("option_lines") or []
        if qtype in {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
        } and len([line for line in option_lines if str(line).strip()]) < 2:
            self.add_error("option_lines", "Agrega al menos 2 opciones.")
        visibility_question = cleaned_data.get("visibility_question")
        if not visibility_question:
            cleaned_data["visibility_operator"] = SurveyQuestion.VisibilityOperator.ALWAYS
            cleaned_data["visibility_option"] = None
            cleaned_data["visibility_value"] = ""
        elif cleaned_data.get("visibility_operator") == SurveyQuestion.VisibilityOperator.ALWAYS:
            cleaned_data["visibility_operator"] = SurveyQuestion.VisibilityOperator.EQUALS
        visibility_option = cleaned_data.get("visibility_option")
        if visibility_option and visibility_question and visibility_option.question_id != visibility_question.pk:
            self.add_error("visibility_option", "La opción debe pertenecer a la pregunta condicionante.")
        return cleaned_data


class SurveySectionBuilderForm(forms.ModelForm):
    class Meta:
        model = SurveySection
        fields = ("title", "description")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control form-control-solid"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "class": "form-control form-control-solid"}
            ),
        }


class DynamicSurveyResponseForm(forms.Form):
    def __init__(self, *args, survey, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        self.questions = list(
            survey.questions.filter(is_active=True)
            .select_related("section")
            .prefetch_related("options")
            .order_by("section__order", "order", "id")
        )
        for question in self.questions:
            self.fields[self.field_name(question)] = self.build_field(question)
            if question.question_type == SurveyQuestion.QuestionType.LOCATION:
                self.fields[self.lat_field_name(question)] = forms.DecimalField(
                    required=False,
                    max_digits=9,
                    decimal_places=6,
                    widget=forms.HiddenInput(),
                )
                self.fields[self.lng_field_name(question)] = forms.DecimalField(
                    required=False,
                    max_digits=9,
                    decimal_places=6,
                    widget=forms.HiddenInput(),
                )
        self._apply_widget_classes()

    @staticmethod
    def field_name(question):
        return f"question_{question.pk}"

    @staticmethod
    def lat_field_name(question):
        return f"question_{question.pk}_lat"

    @staticmethod
    def lng_field_name(question):
        return f"question_{question.pk}_lng"

    def build_field(self, question):
        kwargs = {
            "label": question.text,
            "required": question.is_required and not question.visibility_question_id,
            "help_text": question.help_text,
        }
        qtype = question.question_type
        choices = [(option.pk, option.label) for option in question.options.filter(is_active=True)]
        if qtype == SurveyQuestion.QuestionType.LONG_TEXT:
            return forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), **kwargs)
        if qtype == SurveyQuestion.QuestionType.NUMBER:
            return forms.DecimalField(**kwargs)
        if qtype == SurveyQuestion.QuestionType.DATE:
            return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **kwargs)
        if qtype == SurveyQuestion.QuestionType.TIME:
            return forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}), **kwargs)
        if qtype == SurveyQuestion.QuestionType.YES_NO:
            return forms.ChoiceField(
                choices=(("Sí", "Sí"), ("No", "No")),
                widget=SurveyChoiceRadioSelect,
                **kwargs,
            )
        if qtype == SurveyQuestion.QuestionType.SINGLE_CHOICE:
            return forms.ChoiceField(choices=choices, widget=SurveyChoiceRadioSelect, **kwargs)
        if qtype == SurveyQuestion.QuestionType.MULTIPLE_CHOICE:
            return forms.MultipleChoiceField(
                choices=choices, widget=SurveyChoiceCheckboxSelectMultiple, **kwargs
            )
        if qtype == SurveyQuestion.QuestionType.SCALE_5:
            return forms.ChoiceField(
                choices=[(str(i), str(i)) for i in range(1, 6)],
                widget=SurveyScaleRadioSelect,
                **kwargs,
            )
        if qtype == SurveyQuestion.QuestionType.SCALE_10:
            return forms.ChoiceField(
                choices=[(str(i), str(i)) for i in range(1, 11)],
                widget=SurveyScaleRadioSelect,
                **kwargs,
            )
        if qtype == SurveyQuestion.QuestionType.EMAIL:
            return forms.EmailField(**kwargs)
        if qtype == SurveyQuestion.QuestionType.PHONE:
            return forms.CharField(widget=forms.TextInput(attrs={"type": "tel"}), **kwargs)
        if qtype == SurveyQuestion.QuestionType.FILE:
            return forms.FileField(**kwargs)
        if qtype == SurveyQuestion.QuestionType.IMAGE:
            return forms.ImageField(**kwargs)
        if qtype == SurveyQuestion.QuestionType.LOCATION:
            return forms.CharField(
                required=False,
                label=question.text,
                help_text=question.help_text,
                widget=LeafletMapWidget(
                    lat_field=self.lat_field_name(question),
                    lng_field=self.lng_field_name(question),
                    attrs={"column": 12},
                ),
            )
        return forms.CharField(**kwargs)

    def clean(self):
        cleaned_data = super().clean()
        for question in self.questions:
            visible = self.is_question_visible(question, cleaned_data)
            if question.visibility_question_id and question.is_required and visible:
                value = cleaned_data.get(self.field_name(question))
                if question.question_type == SurveyQuestion.QuestionType.LOCATION:
                    value = cleaned_data.get(self.lat_field_name(question)) and cleaned_data.get(
                        self.lng_field_name(question)
                    )
                if value in (None, "", []):
                    self.add_error(self.field_name(question), "Esta pregunta es obligatoria.")
            if question.question_type != SurveyQuestion.QuestionType.LOCATION:
                continue
            lat = cleaned_data.get(self.lat_field_name(question))
            lng = cleaned_data.get(self.lng_field_name(question))
            if question.is_required and visible and (lat is None or lng is None):
                self.add_error(self.field_name(question), "Selecciona una ubicación en el mapa.")
        return cleaned_data

    def is_question_visible(self, question, cleaned_data):
        if not question.visibility_question_id:
            return True
        parent = question.visibility_question
        parent_value = cleaned_data.get(self.field_name(parent))
        if parent_value in (None, "", []):
            return False
        expected = str(question.visibility_option_id or question.visibility_value or "")
        if isinstance(parent_value, (list, tuple)):
            matched = expected in [str(value) for value in parent_value]
        else:
            matched = str(parent_value) == expected
        if question.visibility_operator == SurveyQuestion.VisibilityOperator.NOT_EQUALS:
            return not matched
        return matched

    def grouped_bound_fields(self):
        groups = []
        current_key = object()
        current = None
        for question in self.questions:
            section = question.section
            key = section.pk if section else None
            if key != current_key:
                current_key = key
                current = {
                    "section": section,
                    "fields": [],
                }
                groups.append(current)
            current["fields"].append(
                {
                    "question": question,
                    "field": self[self.field_name(question)],
                    "field_name": self.field_name(question),
                    "condition_question_name": (
                        self.field_name(question.visibility_question)
                        if question.visibility_question_id
                        else ""
                    ),
                    "condition_operator": question.visibility_operator,
                    "condition_expected": str(
                        question.visibility_option_id or question.visibility_value or ""
                    ),
                }
            )
        return groups

    def _apply_widget_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, SurveyScaleRadioSelect):
                widget.attrs["class"] = f"{existing} survey-scale-input survey-choice-input".strip()
                continue
            if isinstance(widget, (SurveyChoiceRadioSelect, SurveyChoiceCheckboxSelectMultiple)):
                widget.attrs["class"] = (
                    f"{existing} form-check-input survey-choice-input".strip()
                )
                continue
            if isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                widget.attrs["class"] = f"{existing} survey-choice-input".strip()
                continue
            if isinstance(widget, forms.FileInput):
                widget.attrs["class"] = f"{existing} form-control survey-file-input".strip()
                continue
            if isinstance(widget, (forms.HiddenInput, LeafletMapWidget)):
                continue
            widget.attrs["class"] = f"{existing} form-control form-control-lg survey-control".strip()
