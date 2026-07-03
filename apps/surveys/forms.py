import json

from django import forms
from django.utils.text import slugify
from django_select2.forms import ModelSelect2MultipleWidget
from superadmin.forms import ModelForm

from core.form_policies import ConditionalPolicy, FieldValue, Not, dumps_for_script
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
    SurveyRankingWidget,
    SurveyScaleRadioSelect,
)


class SurveyForm(ModelForm):
    class Meta:
        model = Survey
        fieldsets = {
            "Encuesta": (
                ("title", "slug"),
                ("description",),
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
            "all_users_can_respond": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
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

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("all_users_can_respond"):
            cleaned_data["assigned_users"] = self.fields["assigned_users"].queryset.none()
        return cleaned_data


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


class SurveyVisibilityOperatorSelect(forms.Select):
    """Marks operators that only make sense for a numeric source question.

    The builder JS (builder_form.js) reads ``data-numeric-only`` to hide
    those options unless the currently selected ``visibility_question`` is
    of a numeric type.
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw_value = getattr(value, "value", value)
        if raw_value in SurveyQuestion.NUMERIC_VISIBILITY_OPERATORS:
            option["attrs"]["data-numeric-only"] = "true"
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
            "allow_other",
            "min_selections",
            "max_selections",
            "min_value",
            "max_value",
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
            "allow_other": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "min_selections": forms.NumberInput(
                attrs={"class": "form-control form-control-solid", "min": 0}
            ),
            "max_selections": forms.NumberInput(
                attrs={"class": "form-control form-control-solid", "min": 0}
            ),
            "min_value": forms.NumberInput(
                attrs={"class": "form-control form-control-solid", "step": "any"}
            ),
            "max_value": forms.NumberInput(
                attrs={"class": "form-control form-control-solid", "step": "any"}
            ),
            "visibility_operator": SurveyVisibilityOperatorSelect(
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
        form_policies = (
            ConditionalPolicy(
                source="question_type",
                operator="in",
                value=(
                    SurveyQuestion.QuestionType.SINGLE_CHOICE,
                    SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                    SurveyQuestion.QuestionType.RANKING,
                ),
                targets=("option_lines",),
                effects=("show", "disable", "clear"),
            ),
            ConditionalPolicy(
                source="question_type",
                operator="in",
                value=(
                    SurveyQuestion.QuestionType.SINGLE_CHOICE,
                    SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                ),
                targets=("allow_other",),
                effects=("show", "disable", "clear"),
            ),
            ConditionalPolicy(
                source="question_type",
                operator="equals",
                value=SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                targets=("min_selections", "max_selections"),
                effects=("show", "disable", "clear"),
            ),
            ConditionalPolicy(
                source="question_type",
                operator="equals",
                value=SurveyQuestion.QuestionType.NUMBER,
                targets=("min_value", "max_value"),
                effects=("show", "disable", "clear"),
            ),
        )

    def __init__(self, *args, survey=None, **kwargs):
        super().__init__(*args, **kwargs)
        if survey is None and self.instance and self.instance.pk:
            survey = self.instance.survey
        self.survey = survey
        if self.survey is not None:
            self.instance.survey = self.survey
        self.fields["visibility_operator"].required = False
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
        if self.survey is not None:
            self.instance.survey = self.survey
        qtype = cleaned_data.get("question_type")
        option_lines = cleaned_data.get("option_lines") or []
        if qtype in {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
            SurveyQuestion.QuestionType.RANKING,
        } and len([line for line in option_lines if str(line).strip()]) < 2:
            self.add_error("option_lines", "Agrega al menos 2 opciones.")
        allow_other = cleaned_data.get("allow_other")
        if allow_other and qtype not in {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
        }:
            self.add_error(
                "allow_other", 'La opción "Otro" solo aplica a preguntas de selección única o múltiple.'
            )
        min_selections = cleaned_data.get("min_selections")
        max_selections = cleaned_data.get("max_selections")
        if qtype != SurveyQuestion.QuestionType.MULTIPLE_CHOICE:
            if min_selections is not None or max_selections is not None:
                self.add_error(
                    "min_selections",
                    "Los límites de selección solo aplican a preguntas de selección múltiple.",
                )
        elif min_selections is not None and max_selections is not None and min_selections > max_selections:
            self.add_error("max_selections", "El máximo debe ser mayor o igual al mínimo.")
        min_value = cleaned_data.get("min_value")
        max_value = cleaned_data.get("max_value")
        if qtype != SurveyQuestion.QuestionType.NUMBER:
            if min_value is not None or max_value is not None:
                self.add_error(
                    "min_value", "Los límites numéricos solo aplican a preguntas de tipo número."
                )
        elif min_value is not None and max_value is not None and min_value > max_value:
            self.add_error("max_value", "El valor máximo debe ser mayor o igual al mínimo.")
        section = cleaned_data.get("section")
        if section and self.survey is not None and section.survey_id != self.survey.pk:
            self.add_error("section", "La sección debe pertenecer a la misma encuesta.")
        visibility_question = cleaned_data.get("visibility_question")
        if not visibility_question:
            cleaned_data["visibility_operator"] = SurveyQuestion.VisibilityOperator.ALWAYS
            cleaned_data["visibility_option"] = None
            cleaned_data["visibility_value"] = ""
        elif (
            not cleaned_data.get("visibility_operator")
            or cleaned_data.get("visibility_operator") == SurveyQuestion.VisibilityOperator.ALWAYS
        ):
            cleaned_data["visibility_operator"] = SurveyQuestion.VisibilityOperator.EQUALS
        if (
            visibility_question
            and self.survey is not None
            and visibility_question.survey_id != self.survey.pk
        ):
            self.add_error(
                "visibility_question",
                "La pregunta condicionante debe pertenecer a la misma encuesta.",
            )
        visibility_option = cleaned_data.get("visibility_option")
        if visibility_option and visibility_question and visibility_option.question_id != visibility_question.pk:
            self.add_error("visibility_option", "La opción debe pertenecer a la pregunta condicionante.")
        if cleaned_data.get("visibility_operator") in SurveyQuestion.NUMERIC_VISIBILITY_OPERATORS and (
            not visibility_question or visibility_question.question_type not in SurveyQuestion.NUMERIC_QUESTION_TYPES
        ):
            self.add_error(
                "visibility_operator",
                "Este operador solo aplica cuando la pregunta condicionante es numérica.",
            )
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
    # Sentinel choice value for the "Otro" free-text option on single/multiple
    # choice questions with ``allow_other`` — never collides with a real
    # SurveyOption pk (those are posted as integers).
    OTHER_VALUE = "other"

    def __init__(self, *args, survey, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        # Optional identity fields for public, non-anonymous surveys answered
        # by a visitor who isn't logged in (there is no other way to know
        # who responded).
        self.include_respondent_fields = (
            not survey.requires_login
            and not survey.is_anonymous
            and not (user is not None and user.is_authenticated)
        )
        if self.include_respondent_fields:
            self.fields["respondent_name"] = forms.CharField(
                label="Nombre",
                required=False,
                max_length=180,
            )
            self.fields["respondent_email"] = forms.EmailField(
                label="Correo electrónico",
                required=False,
            )
        self.questions = list(
            survey.questions.filter(is_active=True)
            .select_related("section")
            .prefetch_related("options")
            .order_by("section__order", "order", "id")
        )
        self.visible_question_count = len(self.questions)
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
            if question.allow_other and question.question_type in SurveyQuestion.OTHER_ALLOWED_QUESTION_TYPES:
                self.fields[self.other_field_name(question)] = forms.CharField(
                    label="",
                    required=False,
                    max_length=240,
                    widget=forms.TextInput(attrs={"placeholder": "Escribe tu respuesta"}),
                )
        self._apply_widget_classes()
        self.conditional_policies_json = dumps_for_script(self.build_conditional_policies())

    @staticmethod
    def field_name(question):
        return f"question_{question.pk}"

    @staticmethod
    def lat_field_name(question):
        return f"question_{question.pk}_lat"

    @staticmethod
    def lng_field_name(question):
        return f"question_{question.pk}_lng"

    @staticmethod
    def other_field_name(question):
        return f"question_{question.pk}_other"

    def build_field(self, question):
        kwargs = {
            "label": question.text,
            "required": question.is_required and not question.visibility_question_id,
            "help_text": question.help_text,
        }
        qtype = question.question_type
        choices = [(option.pk, option.label) for option in question.options.filter(is_active=True)]
        if question.allow_other and qtype in SurveyQuestion.OTHER_ALLOWED_QUESTION_TYPES:
            choices = choices + [(self.OTHER_VALUE, "Otro")]
        if qtype == SurveyQuestion.QuestionType.LONG_TEXT:
            return forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), **kwargs)
        if qtype == SurveyQuestion.QuestionType.NUMBER:
            error_messages = {}
            if question.min_value is not None:
                error_messages["min_value"] = f"El valor debe ser mayor o igual a {question.min_value}."
            if question.max_value is not None:
                error_messages["max_value"] = f"El valor debe ser menor o igual a {question.max_value}."
            return forms.DecimalField(
                min_value=question.min_value,
                max_value=question.max_value,
                error_messages=error_messages,
                **kwargs,
            )
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
        if qtype == SurveyQuestion.QuestionType.NPS:
            return forms.ChoiceField(
                choices=[(str(i), str(i)) for i in range(0, 11)],
                widget=SurveyScaleRadioSelect,
                **kwargs,
            )
        if qtype == SurveyQuestion.QuestionType.RANKING:
            option_pairs = [
                (option.value, option.label) for option in question.options.filter(is_active=True)
            ]
            return forms.CharField(
                label=question.text,
                help_text=question.help_text,
                required=False,
                widget=SurveyRankingWidget(options=option_pairs),
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
            self._clean_ranking_question(question, cleaned_data, visible)
            self._clean_other_option(question, cleaned_data, visible)
            self._clean_selection_limits(question, cleaned_data, visible)
            if question.question_type != SurveyQuestion.QuestionType.LOCATION:
                continue
            lat = cleaned_data.get(self.lat_field_name(question))
            lng = cleaned_data.get(self.lng_field_name(question))
            if question.is_required and visible and (lat is None or lng is None):
                self.add_error(self.field_name(question), "Selecciona una ubicación en el mapa.")
        return cleaned_data

    def _clean_ranking_question(self, question, cleaned_data, visible):
        """Validate/normalize a RANKING answer.

        The field is always built with ``required=False`` (its widget's
        real value lives in a hidden input, see ``SurveyRankingWidget``), so
        both the "required" and "full permutation of the question's
        options" checks happen here, mirroring how LOCATION validates its
        lat/lng pair below.
        """
        if question.question_type != SurveyQuestion.QuestionType.RANKING:
            return
        raw = cleaned_data.get(self.field_name(question))
        normalized = self._normalize_ranking_value(question, raw)
        if raw and normalized is None:
            self.add_error(self.field_name(question), "El orden de las opciones no es válido.")
        elif question.is_required and visible and normalized is None:
            self.add_error(self.field_name(question), "Ordena todas las opciones para continuar.")
        elif normalized is not None:
            cleaned_data[self.field_name(question)] = json.dumps(normalized)

    def _normalize_ranking_value(self, question, raw):
        """Return the submitted ranking as a list of option values, or
        ``None`` when it isn't an exact permutation of the question's
        active option values (missing, extra, duplicated or tampered).
        """
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed, list):
            return None
        submitted = [str(item) for item in parsed]
        option_values = [option.value for option in question.options.filter(is_active=True)]
        if len(submitted) != len(set(submitted)) or sorted(submitted) != sorted(option_values):
            return None
        return submitted

    def _clean_other_option(self, question, cleaned_data, visible):
        """Require the companion free-text field when "Otro" is selected."""
        if not (
            visible
            and question.allow_other
            and question.question_type in SurveyQuestion.OTHER_ALLOWED_QUESTION_TYPES
        ):
            return
        selected = cleaned_data.get(self.field_name(question))
        if question.question_type == SurveyQuestion.QuestionType.SINGLE_CHOICE:
            other_selected = selected == self.OTHER_VALUE
        else:
            other_selected = self.OTHER_VALUE in (selected or [])
        other_text = (cleaned_data.get(self.other_field_name(question)) or "").strip()
        if other_selected and not other_text:
            self.add_error(self.other_field_name(question), 'Escribe tu respuesta para "Otro".')

    def _clean_selection_limits(self, question, cleaned_data, visible):
        """Enforce min_selections/max_selections on a multiple_choice answer."""
        if question.question_type != SurveyQuestion.QuestionType.MULTIPLE_CHOICE or not visible:
            return
        selected = cleaned_data.get(self.field_name(question)) or []
        count = len(selected)
        if (
            question.min_selections is not None
            and count < question.min_selections
            and (count or question.is_required)
        ):
            self.add_error(
                self.field_name(question),
                f"Selecciona al menos {question.min_selections} opciones.",
            )
        if question.max_selections is not None and count > question.max_selections:
            self.add_error(
                self.field_name(question),
                f"Selecciona como máximo {question.max_selections} opciones.",
            )

    def is_question_visible(self, question, cleaned_data):
        if not question.visibility_question_id:
            return True
        parent = question.visibility_question
        parent_value = cleaned_data.get(self.field_name(parent))
        if parent_value in (None, "", []):
            return False
        operator = question.visibility_operator
        if operator in SurveyQuestion.NUMERIC_VISIBILITY_OPERATORS:
            try:
                actual_number = float(parent_value)
                expected_number = float(question.visibility_value)
            except (TypeError, ValueError):
                return False
            if operator == SurveyQuestion.VisibilityOperator.GREATER_THAN:
                return actual_number > expected_number
            return actual_number < expected_number
        expected = str(question.visibility_option_id or question.visibility_value or "")
        if isinstance(parent_value, (list, tuple)):
            matched = expected in [str(value) for value in parent_value]
        else:
            matched = str(parent_value) == expected
        if operator == SurveyQuestion.VisibilityOperator.NOT_EQUALS:
            return not matched
        return matched

    def grouped_bound_fields(self):
        groups = []
        current_key = object()
        current = None
        question_number = 0
        for question in self.questions:
            question_number += 1
            section = question.section
            key = section.pk if section else None
            if key != current_key:
                current_key = key
                current = {
                    "section": section,
                    "fields": [],
                }
                groups.append(current)
            other_field_name = self.other_field_name(question)
            current["fields"].append(
                {
                    "question": question,
                    "question_number": question_number,
                    "field": self[self.field_name(question)],
                    "field_name": self.field_name(question),
                    "other_field": self[other_field_name] if other_field_name in self.fields else None,
                }
            )
        return groups

    # Client-side operator equivalents in core.form_policies / conditional_fields.js
    # for each SurveyQuestion.VisibilityOperator that has a direct match.
    _CLIENT_OPERATOR_MAP = {
        SurveyQuestion.VisibilityOperator.EQUALS: "equals",
        SurveyQuestion.VisibilityOperator.NOT_EQUALS: "not_equals",
        SurveyQuestion.VisibilityOperator.GREATER_THAN: ">",
        SurveyQuestion.VisibilityOperator.LESS_THAN: "<",
    }

    def build_conditional_policies(self):
        """Emit question-visibility rules as the global form-policies engine's
        client JSON (see core/form_policies.py + conditional_fields.js), so
        respond.html can drive show/hide with the same shared engine used by
        normal forms instead of bespoke inline JS.

        Server-side visibility (is_question_visible) stays authoritative for
        validation; this only mirrors it for the client preview.
        """
        policies = []
        for question in self.questions:
            if not question.visibility_question_id:
                continue
            parent = question.visibility_question
            source = self.field_name(parent)
            targets = [self.field_name(question)]
            if question.question_type == SurveyQuestion.QuestionType.LOCATION:
                # The map widget doesn't render an input named after the
                # main field; the actual submitted data lives in the
                # lat/lng hidden fields, so those need to be disabled too
                # when the question is hidden.
                targets.extend([self.lat_field_name(question), self.lng_field_name(question)])
            operator = question.visibility_operator
            expected = str(question.visibility_option_id or question.visibility_value or "")
            client_operator = self._CLIENT_OPERATOR_MAP.get(
                operator, "equals"
            )
            if (
                parent.question_type == SurveyQuestion.QuestionType.MULTIPLE_CHOICE
                and operator
                in (
                    SurveyQuestion.VisibilityOperator.EQUALS,
                    SurveyQuestion.VisibilityOperator.NOT_EQUALS,
                )
            ):
                # A multiple_choice source submits a list of checked option
                # ids. Server-side is_question_visible treats equals/not_equals
                # as list-membership ("is the expected option among the
                # checked ones?"), not exact-array equality, so mirror that
                # with the engine's "contains" operator (negated via Not()
                # for not_equals — the engine has no built-in "not_contains").
                condition = FieldValue(source, "contains", expected)
                if operator == SurveyQuestion.VisibilityOperator.NOT_EQUALS:
                    condition = Not(condition)
            else:
                condition = FieldValue(source, client_operator, expected)
            policy = ConditionalPolicy(
                source=source,
                targets=targets,
                condition=condition,
                # "show" without "hide" means: suppress (hide + disable) the
                # target when the condition is NOT active, matching the old
                # bespoke JS which hid+disabled the card without clearing
                # any previously entered value.
                effects=("show", "disable"),
            )
            client_policy = policy.as_client()
            if client_policy is not None:
                policies.append(client_policy)
        for question in self.questions:
            if not (
                question.allow_other and question.question_type in SurveyQuestion.OTHER_ALLOWED_QUESTION_TYPES
            ):
                continue
            source = self.field_name(question)
            operator = (
                "contains"
                if question.question_type == SurveyQuestion.QuestionType.MULTIPLE_CHOICE
                else "equals"
            )
            other_policy = ConditionalPolicy(
                source=source,
                targets=[self.other_field_name(question)],
                condition=FieldValue(source, operator, self.OTHER_VALUE),
                effects=("show", "disable"),
            )
            client_other_policy = other_policy.as_client()
            if client_other_policy is not None:
                policies.append(client_other_policy)
        return policies

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
            if isinstance(widget, (forms.HiddenInput, LeafletMapWidget, SurveyRankingWidget)):
                continue
            widget.attrs["class"] = f"{existing} form-control form-control-lg survey-control".strip()
