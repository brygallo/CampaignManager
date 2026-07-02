import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from tracing.models import BaseModel

from apps.locations.models import Canton, Parish, Province


class Survey(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicada"
        CLOSED = "closed", "Cerrada"
        ARCHIVED = "archived", "Archivada"

    title = models.CharField("Título", max_length=180)
    slug = models.SlugField("Slug", max_length=220, unique=True)
    description = models.TextField("Descripción", blank=True)
    status = models.CharField(
        "Estado", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    starts_at = models.DateTimeField("Inicio", null=True, blank=True)
    ends_at = models.DateTimeField("Fin", null=True, blank=True)
    is_anonymous = models.BooleanField("Anónima", default=False)
    requires_login = models.BooleanField("Requiere inicio de sesión", default=True)
    allow_multiple_responses = models.BooleanField("Permite varias respuestas", default=False)
    thank_you_message = models.CharField(
        "Mensaje de confirmación",
        max_length=240,
        blank=True,
        default="Gracias. Tu respuesta fue registrada.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_surveys",
        verbose_name="Creada por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Encuesta"
        verbose_name_plural = "Encuestas"
        ordering = ["-created_date"]
        permissions = (
            ("publish_survey", "Puede publicar/cerrar encuestas"),
            ("view_survey_results", "Puede ver resultados de encuestas"),
            ("export_survey_results", "Puede exportar resultados de encuestas"),
        )

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        from django.utils import timezone

        now = timezone.now()
        if self.status != self.Status.PUBLISHED:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        return True

    def get_absolute_url(self):
        return reverse("site:surveys_survey_", kwargs={"slug": self.slug})

    def get_public_url(self):
        return reverse("surveys:respond", kwargs={"slug": self.slug})

    def get_results_url(self):
        return reverse("surveys:results", kwargs={"pk": self.pk})


class SurveySection(BaseModel):
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="sections", verbose_name="Encuesta"
    )
    title = models.CharField("Título", max_length=180)
    description = models.TextField("Descripción", blank=True)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Sección de encuesta"
        verbose_name_plural = "Secciones de encuesta"
        ordering = ["survey", "order", "title"]

    def __str__(self):
        return f"{self.survey} - {self.title}"


class SurveyQuestion(BaseModel):
    class QuestionType(models.TextChoices):
        SHORT_TEXT = "short_text", "Texto corto"
        LONG_TEXT = "long_text", "Texto largo"
        NUMBER = "number", "Número"
        DATE = "date", "Fecha"
        TIME = "time", "Hora"
        YES_NO = "yes_no", "Sí/No"
        SINGLE_CHOICE = "single_choice", "Selección única"
        MULTIPLE_CHOICE = "multiple_choice", "Selección múltiple"
        SCALE_5 = "scale_5", "Escala 1-5"
        SCALE_10 = "scale_10", "Escala 1-10"
        EMAIL = "email", "Correo"
        PHONE = "phone", "Teléfono"
        FILE = "file", "Archivo"
        IMAGE = "image", "Imagen"
        LOCATION = "location", "Ubicación GPS"

    class VisibilityOperator(models.TextChoices):
        ALWAYS = "always", "Siempre visible"
        EQUALS = "equals", "Mostrar si es igual a"
        NOT_EQUALS = "not_equals", "Mostrar si es distinto de"

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="questions", verbose_name="Encuesta"
    )
    section = models.ForeignKey(
        SurveySection,
        on_delete=models.SET_NULL,
        related_name="questions",
        verbose_name="Sección",
        null=True,
        blank=True,
    )
    text = models.CharField("Pregunta", max_length=300)
    help_text = models.CharField("Ayuda", max_length=240, blank=True)
    question_type = models.CharField(
        "Tipo", max_length=30, choices=QuestionType.choices, default=QuestionType.SHORT_TEXT
    )
    is_required = models.BooleanField("Obligatoria", default=False)
    order = models.PositiveSmallIntegerField("Orden", default=0)
    visibility_question = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="dependent_questions",
        verbose_name="Depende de",
        null=True,
        blank=True,
    )
    visibility_operator = models.CharField(
        "Condición",
        max_length=20,
        choices=VisibilityOperator.choices,
        default=VisibilityOperator.ALWAYS,
    )
    visibility_option = models.ForeignKey(
        "SurveyOption",
        on_delete=models.SET_NULL,
        related_name="visible_questions",
        verbose_name="Opción esperada",
        null=True,
        blank=True,
    )
    visibility_value = models.CharField("Valor esperado", max_length=180, blank=True)

    class Meta:
        verbose_name = "Pregunta de encuesta"
        verbose_name_plural = "Preguntas de encuesta"
        ordering = ["survey", "section__order", "order", "id"]

    def __str__(self):
        return self.text

    @property
    def uses_options(self):
        return self.question_type in {
            self.QuestionType.SINGLE_CHOICE,
            self.QuestionType.MULTIPLE_CHOICE,
        }

    def clean(self):
        super().clean()
        if self.section_id and self.section.survey_id != self.survey_id:
            raise ValidationError({"section": "La sección debe pertenecer a la misma encuesta."})
        if self.visibility_question_id and self.visibility_question.survey_id != self.survey_id:
            raise ValidationError(
                {"visibility_question": "La pregunta condicionante debe pertenecer a la misma encuesta."}
            )
        if self.visibility_question_id == self.pk:
            raise ValidationError({"visibility_question": "Una pregunta no puede depender de sí misma."})
        if self.visibility_option_id and self.visibility_option.question_id != self.visibility_question_id:
            raise ValidationError(
                {"visibility_option": "La opción debe pertenecer a la pregunta condicionante."}
            )


class SurveyOption(BaseModel):
    question = models.ForeignKey(
        SurveyQuestion, on_delete=models.CASCADE, related_name="options", verbose_name="Pregunta"
    )
    label = models.CharField("Opción", max_length=180)
    value = models.CharField("Valor", max_length=180, blank=True)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Opción de encuesta"
        verbose_name_plural = "Opciones de encuesta"
        ordering = ["question", "order", "label"]

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        if not self.value:
            self.value = self.label
        super().save(*args, **kwargs)


class SurveyResponse(BaseModel):
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="responses", verbose_name="Encuesta"
    )
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="survey_responses",
        verbose_name="Usuario",
        null=True,
        blank=True,
    )
    respondent_name = models.CharField("Nombre", max_length=180, blank=True)
    respondent_email = models.EmailField("Correo", blank=True)
    token = models.UUIDField("Token", default=uuid.uuid4, unique=True, editable=False)
    submitted_at = models.DateTimeField("Enviada", auto_now_add=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.TextField("Navegador", blank=True)

    class Meta:
        verbose_name = "Respuesta de encuesta"
        verbose_name_plural = "Respuestas de encuesta"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.survey} - {self.submitted_at:%d/%m/%Y %H:%M}"


class SurveyAnswer(BaseModel):
    response = models.ForeignKey(
        SurveyResponse, on_delete=models.CASCADE, related_name="answers", verbose_name="Respuesta"
    )
    question = models.ForeignKey(
        SurveyQuestion, on_delete=models.PROTECT, related_name="answers", verbose_name="Pregunta"
    )
    value_text = models.TextField("Respuesta", blank=True)
    value_number = models.DecimalField(
        "Número", max_digits=14, decimal_places=2, null=True, blank=True
    )
    value_date = models.DateField("Fecha", null=True, blank=True)
    value_time = models.TimeField("Hora", null=True, blank=True)
    value_file = models.FileField(
        "Archivo", upload_to="surveys/answers/files/", null=True, blank=True
    )
    selected_options = models.ManyToManyField(
        SurveyOption, related_name="answers", verbose_name="Opciones", blank=True
    )
    latitude = models.DecimalField("Latitud", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        "Longitud", max_digits=9, decimal_places=6, null=True, blank=True
    )

    class Meta:
        verbose_name = "Respuesta a pregunta"
        verbose_name_plural = "Respuestas a preguntas"
        ordering = ["response", "question__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["response", "question"], name="surveys_unique_answer_per_question"
            )
        ]

    def __str__(self):
        return f"{self.question}: {self.display_value}"

    @property
    def display_value(self):
        question_type = self.question.question_type
        if question_type in {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
        }:
            return ", ".join(self.selected_options.values_list("label", flat=True))
        if question_type == SurveyQuestion.QuestionType.NUMBER:
            return "" if self.value_number is None else str(self.value_number)
        if question_type == SurveyQuestion.QuestionType.DATE:
            return "" if self.value_date is None else self.value_date.isoformat()
        if question_type == SurveyQuestion.QuestionType.TIME:
            return "" if self.value_time is None else self.value_time.strftime("%H:%M")
        if question_type in {SurveyQuestion.QuestionType.FILE, SurveyQuestion.QuestionType.IMAGE}:
            return self.value_file.name if self.value_file else ""
        if question_type == SurveyQuestion.QuestionType.LOCATION:
            if self.latitude is None or self.longitude is None:
                return ""
            return f"{self.latitude}, {self.longitude}"
        return self.value_text


class ElectoralDignity(BaseModel):
    class Scope(models.TextChoices):
        PROVINCE = "province", "Provincia"
        CANTON = "canton", "Cantón"
        DISTRICT = "district", "Circunscripción"
        PARISH = "parish", "Parroquia"

    class ParishKindRule(models.TextChoices):
        ALL = "all", "Todas"
        URBAN = "urban", "Solo urbanas"
        RURAL = "rural", "Solo rurales"

    name = models.CharField("Dignidad", max_length=140, unique=True)
    scope = models.CharField("Ámbito", max_length=20, choices=Scope.choices)
    parish_kind_rule = models.CharField(
        "Tipo de parroquia",
        max_length=20,
        choices=ParishKindRule.choices,
        default=ParishKindRule.ALL,
    )
    seats = models.PositiveSmallIntegerField("Escaños", default=1)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Dignidad electoral"
        verbose_name_plural = "Dignidades electorales"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class ElectoralVenue(BaseModel):
    parish = models.ForeignKey(
        Parish, on_delete=models.PROTECT, related_name="electoral_venues", verbose_name="Parroquia"
    )
    name = models.CharField("Recinto electoral", max_length=180)

    class Meta:
        verbose_name = "Recinto electoral"
        verbose_name_plural = "Recintos electorales"
        ordering = ["parish__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parish", "name"], name="surveys_unique_electoral_venue_per_parish"
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.parish.name}"


class ElectoralTable(BaseModel):
    class Gender(models.TextChoices):
        FEMALE = "F", "Femenino"
        MALE = "M", "Masculino"
        MIXED = "X", "Mixta"

    venue = models.ForeignKey(
        ElectoralVenue, on_delete=models.PROTECT, related_name="tables", verbose_name="Recinto"
    )
    number = models.CharField("Mesa", max_length=24)
    gender = models.CharField("Género", max_length=1, choices=Gender.choices, default=Gender.MIXED)

    class Meta:
        verbose_name = "Mesa electoral"
        verbose_name_plural = "Mesas electorales"
        ordering = ["venue__parish__name", "venue__name", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "number", "gender"], name="surveys_unique_electoral_table"
            )
        ]

    def __str__(self):
        return f"Mesa {self.number} {self.get_gender_display()} - {self.venue.name}"

    @property
    def parish(self):
        return self.venue.parish

    @property
    def canton(self):
        return self.venue.parish.canton

    @property
    def province(self):
        return self.venue.parish.canton.province


class ElectoralTableAssignment(BaseModel):
    table = models.ForeignKey(
        ElectoralTable,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Mesa",
    )
    watcher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="electoral_table_assignments",
        verbose_name="Veedor",
    )
    notes = models.CharField("Observaciones", max_length=240, blank=True)

    class Meta:
        verbose_name = "Asignación de mesa"
        verbose_name_plural = "Asignaciones de mesas"
        ordering = ["table__venue__parish__name", "table__venue__name", "table__number"]
        constraints = [
            models.UniqueConstraint(
                fields=["table", "watcher"], name="surveys_unique_table_watcher_assignment"
            )
        ]

    def __str__(self):
        return f"{self.watcher} - {self.table}"


class ElectoralDistrict(BaseModel):
    class DistrictKind(models.TextChoices):
        PROVINCE = "province", "Provincia"
        CANTON = "canton", "Cantón"
        URBAN = "urban", "Urbana"
        RURAL = "rural", "Rural"
        PARISH = "parish", "Parroquial"

    dignity = models.ForeignKey(
        ElectoralDignity,
        on_delete=models.CASCADE,
        related_name="districts",
        verbose_name="Dignidad",
    )
    name = models.CharField("Circunscripción", max_length=180)
    kind = models.CharField("Tipo", max_length=20, choices=DistrictKind.choices)
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        related_name="electoral_districts",
        verbose_name="Provincia",
        null=True,
        blank=True,
    )
    canton = models.ForeignKey(
        Canton,
        on_delete=models.PROTECT,
        related_name="electoral_districts",
        verbose_name="Cantón",
        null=True,
        blank=True,
    )
    parishes = models.ManyToManyField(
        Parish,
        related_name="electoral_districts",
        verbose_name="Parroquias",
        blank=True,
    )
    seats = models.PositiveSmallIntegerField("Escaños", default=1)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Circunscripción electoral"
        verbose_name_plural = "Circunscripciones electorales"
        ordering = ["dignity__order", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["dignity", "name"], name="surveys_unique_electoral_district_name"
            )
        ]

    def __str__(self):
        return f"{self.dignity} / {self.name}"

    def contains_parish(self, parish):
        if self.dignity.scope == ElectoralDignity.Scope.PROVINCE:
            return self.province_id == parish.canton.province_id
        if self.dignity.scope == ElectoralDignity.Scope.CANTON:
            return self.canton_id == parish.canton_id
        return self.parishes.filter(pk=parish.pk).exists()


class ElectoralCandidateOption(BaseModel):
    district = models.ForeignKey(
        ElectoralDistrict,
        on_delete=models.CASCADE,
        related_name="candidate_options",
        verbose_name="Circunscripción",
    )
    list_code = models.CharField("Lista", max_length=32)
    candidate_name = models.CharField("Candidato", max_length=180)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Candidatura electoral"
        verbose_name_plural = "Candidaturas electorales"
        ordering = ["district__dignity__order", "district__order", "order", "list_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["district", "list_code", "candidate_name"],
                name="surveys_unique_electoral_candidate_option",
            )
        ]

    def __str__(self):
        return f"{self.district} / {self.list_code} - {self.candidate_name}"


class ElectoralResultReport(BaseModel):
    parish = models.ForeignKey(
        Parish, on_delete=models.PROTECT, related_name="electoral_result_reports", verbose_name="Parroquia"
    )
    venue = models.ForeignKey(
        ElectoralVenue,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Recinto electoral",
    )
    table = models.ForeignKey(
        ElectoralTable,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Mesa",
    )
    dignity = models.ForeignKey(
        ElectoralDignity,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Dignidad",
    )
    district = models.ForeignKey(
        ElectoralDistrict,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Circunscripción",
    )
    watcher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="electoral_result_reports",
        verbose_name="Veedor",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Registro de resultado electoral"
        verbose_name_plural = "Registros de resultados electorales"
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["table", "dignity", "district"],
                name="surveys_unique_electoral_result_report",
            )
        ]

    def __str__(self):
        return f"{self.dignity} - {self.table}"


class ElectoralResultLine(BaseModel):
    class LineType(models.TextChoices):
        CANDIDATE = "candidate", "Candidato"
        BLANK = "blank", "Blancos"
        NULL = "null", "Nulos"

    report = models.ForeignKey(
        ElectoralResultReport,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Registro",
    )
    line_type = models.CharField(
        "Tipo", max_length=20, choices=LineType.choices, default=LineType.CANDIDATE
    )
    list_code = models.CharField("Lista", max_length=32)
    candidate_name = models.CharField("Candidato", max_length=180, blank=True)
    candidate_option = models.ForeignKey(
        ElectoralCandidateOption,
        on_delete=models.PROTECT,
        related_name="result_lines",
        verbose_name="Candidatura",
        null=True,
        blank=True,
    )
    votes = models.PositiveIntegerField("Votos", default=0)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Línea de resultado electoral"
        verbose_name_plural = "Líneas de resultados electorales"
        ordering = ["report", "order", "list_code"]

    def __str__(self):
        return f"{self.list_code} {self.candidate_name}: {self.votes}"
