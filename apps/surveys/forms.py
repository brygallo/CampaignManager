from django import forms
from django.utils.text import slugify
from superadmin.forms import ModelForm

from apps.locations.models import Parish
from core.widgets import LeafletMapWidget

from .models import (
    ElectoralCandidateOption,
    ElectoralDignity,
    ElectoralDistrict,
    ElectoralTable,
    ElectoralTableAssignment,
    ElectoralVenue,
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
            "Confirmación": (
                ("thank_you_message",),
            ),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        title = self.cleaned_data.get("title")
        return slug or slugify(title or "")


class SurveySectionForm(ModelForm):
    class Meta:
        model = SurveySection
        fieldsets = {
            "Sección": (
                ("survey",),
                ("title", "order"),
                ("description",),
                ("is_active",),
            ),
        }


class SurveyQuestionForm(ModelForm):
    class Meta:
        model = SurveyQuestion
        fieldsets = {
            "Pregunta": (
                ("survey", "section"),
                ("text",),
                ("help_text",),
                ("question_type", "order"),
                ("is_required", "is_active"),
            ),
        }


class SurveyOptionForm(ModelForm):
    class Meta:
        model = SurveyOption
        fieldsets = {
            "Opción": (
                ("question",),
                ("label", "value"),
                ("order", "is_active"),
            ),
        }


class ElectoralDignityForm(ModelForm):
    class Meta:
        model = ElectoralDignity
        fieldsets = {
            "Dignidad": (
                ("name", "order"),
                ("scope", "parish_kind_rule"),
                ("seats", "is_active"),
            ),
        }


class ElectoralDistrictForm(ModelForm):
    class Meta:
        model = ElectoralDistrict
        fieldsets = {
            "Circunscripción": (
                ("dignity", "name"),
                ("kind", "order"),
                ("province", "canton"),
                ("parishes",),
                ("seats", "is_active"),
            ),
        }


class ElectoralVenueForm(ModelForm):
    class Meta:
        model = ElectoralVenue
        fieldsets = {
            "Recinto electoral": (
                ("parish",),
                ("name", "is_active"),
            ),
        }


class ElectoralTableForm(ModelForm):
    class Meta:
        model = ElectoralTable
        fieldsets = {
            "Mesa electoral": (
                ("venue",),
                ("number", "gender"),
                ("is_active",),
            ),
        }


class ElectoralTableAssignmentForm(ModelForm):
    class Meta:
        model = ElectoralTableAssignment
        fieldsets = {
            "Asignación": (
                ("table", "watcher"),
                ("notes",),
                ("is_active",),
            ),
        }


class ElectoralCandidateOptionForm(ModelForm):
    class Meta:
        model = ElectoralCandidateOption
        fieldsets = {
            "Candidatura": (
                ("district",),
                ("list_code", "candidate_name"),
                ("order", "is_active"),
            ),
        }


class ElectoralWatcherForm(forms.Form):
    parish = forms.ModelChoiceField(
        label="Parroquia",
        queryset=None,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    venue = forms.ModelChoiceField(
        label="Recinto electoral",
        queryset=ElectoralVenue.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    table = forms.ModelChoiceField(
        label="Mesa",
        queryset=ElectoralTable.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    dignity = forms.ModelChoiceField(
        label="Dignidad a elegir",
        queryset=ElectoralDignity.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    blank_votes = forms.IntegerField(
        label="Votos blancos",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-solid", "min": 0}),
    )
    null_votes = forms.IntegerField(
        label="Votos nulos",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-solid", "min": 0}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parish"].queryset = Parish.objects.filter(is_active=True).order_by(
            "canton__name", "name"
        )
        if self.data.get("parish"):
            self.fields["venue"].queryset = ElectoralVenue.objects.filter(
                parish_id=self.data.get("parish"), is_active=True
            ).order_by("name")
            self.fields["dignity"].queryset = self._dignities_for_parish_id(self.data.get("parish"))
        if self.data.get("venue"):
            self.fields["table"].queryset = ElectoralTable.objects.filter(
                venue_id=self.data.get("venue"), is_active=True
            ).order_by("number", "gender")
        self.candidate_options = ElectoralCandidateOption.objects.none()
        self.district = None
        if self.data.get("parish") and self.data.get("dignity"):
            self.district = resolve_electoral_district(
                parish_id=self.data.get("parish"), dignity_id=self.data.get("dignity")
            )
            if self.district:
                self.candidate_options = self.district.candidate_options.filter(
                    is_active=True
                ).order_by("order", "list_code", "candidate_name")
                for option in self.candidate_options:
                    self.fields[self.vote_field_name(option)] = forms.IntegerField(
                        label=f"{option.list_code} - {option.candidate_name}",
                        min_value=0,
                        initial=0,
                        widget=forms.NumberInput(
                            attrs={"class": "form-control form-control-solid", "min": 0}
                        ),
                    )

    @staticmethod
    def vote_field_name(option):
        return f"candidate_{option.pk}"

    def _dignities_for_parish_id(self, parish_id):
        from apps.locations.models import Parish

        try:
            parish = Parish.objects.select_related("canton__province").get(pk=parish_id)
        except (Parish.DoesNotExist, ValueError, TypeError):
            return ElectoralDignity.objects.none()
        districts = ElectoralDistrict.objects.filter(is_active=True).filter(
            forms.models.Q(province=parish.canton.province)
            | forms.models.Q(canton=parish.canton)
            | forms.models.Q(parishes=parish)
        )
        return (
            ElectoralDignity.objects.filter(districts__in=districts)
            .distinct()
            .order_by("order", "name")
        )

    def clean(self):
        cleaned_data = super().clean()
        parish = cleaned_data.get("parish")
        venue = cleaned_data.get("venue")
        table = cleaned_data.get("table")
        dignity = cleaned_data.get("dignity")
        if venue and parish and venue.parish_id != parish.pk:
            self.add_error("venue", "El recinto no pertenece a la parroquia seleccionada.")
        if table and venue and table.venue_id != venue.pk:
            self.add_error("table", "La mesa no pertenece al recinto seleccionado.")
        if parish and dignity:
            self.district = resolve_electoral_district(parish_id=parish.pk, dignity_id=dignity.pk)
            if not self.district:
                self.add_error("dignity", "No existe una circunscripción configurada para esta parroquia.")
        if self.district and not self.candidate_options.exists():
            self.add_error("dignity", "La circunscripción no tiene candidaturas activas.")
        return cleaned_data


class ElectoralReportFilterForm(forms.Form):
    dignity = forms.ModelChoiceField(
        label="Dignidad",
        queryset=ElectoralDignity.objects.filter(is_active=True).order_by("order", "name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    district = forms.ModelChoiceField(
        label="Circunscripción",
        queryset=ElectoralDistrict.objects.filter(is_active=True).order_by("dignity__order", "name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    parish = forms.ModelChoiceField(
        label="Parroquia",
        queryset=None,
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    venue = forms.ModelChoiceField(
        label="Recinto electoral",
        queryset=ElectoralVenue.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    table = forms.ModelChoiceField(
        label="Mesa",
        queryset=ElectoralTable.objects.filter(is_active=True).order_by("number", "gender"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parish"].queryset = Parish.objects.filter(is_active=True).order_by(
            "canton__name", "name"
        )


def resolve_electoral_district(*, parish_id, dignity_id):
    from apps.locations.models import Parish

    try:
        parish = Parish.objects.select_related("canton__province").get(pk=parish_id)
        dignity = ElectoralDignity.objects.get(pk=dignity_id)
    except (Parish.DoesNotExist, ElectoralDignity.DoesNotExist, ValueError, TypeError):
        return None
    districts = ElectoralDistrict.objects.filter(dignity=dignity, is_active=True)
    if dignity.scope == ElectoralDignity.Scope.PROVINCE:
        return districts.filter(province=parish.canton.province).first()
    if dignity.scope == ElectoralDignity.Scope.CANTON:
        return districts.filter(canton=parish.canton).first()
    return districts.filter(parishes=parish).first()


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
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    visibility_option = forms.ModelChoiceField(
        label="Opción esperada",
        queryset=SurveyOption.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
        help_text="Úsalo cuando la pregunta condicionante es de selección.",
    )
    option_lines = forms.CharField(
        label="Opciones",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Una opción por línea",
                "class": "form-control form-control-solid",
            }
        ),
        help_text="Solo aplica para selección única o múltiple.",
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
            "question_type": forms.Select(attrs={"class": "form-select form-select-solid"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "visibility_operator": forms.Select(attrs={"class": "form-select form-select-solid"}),
            "visibility_value": forms.TextInput(attrs={"class": "form-control form-control-solid"}),
        }

    def __init__(self, *args, survey=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        if self.instance and self.instance.pk and not self.is_bound:
            self.fields["option_lines"].initial = "\n".join(
                self.instance.options.filter(is_active=True).order_by("order").values_list(
                    "label", flat=True
                )
            )
        if survey is not None:
            self.fields["section"].queryset = survey.sections.filter(is_active=True).order_by(
                "order", "title"
            )
            self.fields["visibility_question"].queryset = survey.questions.filter(
                is_active=True
            ).order_by("section__order", "order", "id")
            self.fields["visibility_option"].queryset = SurveyOption.objects.filter(
                question__survey=survey,
                is_active=True,
            ).order_by("question__order", "order", "label")

    def clean(self):
        cleaned_data = super().clean()
        qtype = cleaned_data.get("question_type")
        option_lines = cleaned_data.get("option_lines", "")
        if qtype in {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
        } and len([line for line in option_lines.splitlines() if line.strip()]) < 2:
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
