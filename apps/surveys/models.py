import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from tracing.models import BaseModel


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
    all_users_can_respond = models.BooleanField(
        "Todos los usuarios pueden responder",
        default=False,
        help_text="Si está activo, cualquier usuario autenticado puede responder esta encuesta.",
    )
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
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_surveys",
        verbose_name="Usuarios asignados",
        blank=True,
    )

    class Meta:
        verbose_name = "Encuesta"
        verbose_name_plural = "Encuestas"
        ordering = ["-created_date"]
        permissions = (
            ("publish_survey", "Puede publicar/cerrar encuestas"),
            ("apply_all_surveys", "Puede responder todas las encuestas"),
            ("manage_survey_assignments", "Puede gestionar asignación de encuestas"),
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
        GREATER_THAN = "greater_than", "Mostrar si es mayor que"
        LESS_THAN = "less_than", "Mostrar si es menor que"

    # Operators that only make sense when the conditioning question answers
    # with a comparable numeric value.
    NUMERIC_VISIBILITY_OPERATORS = {VisibilityOperator.GREATER_THAN, VisibilityOperator.LESS_THAN}
    # Question types whose answer can be safely cast to float() for the
    # numeric visibility operators above.
    NUMERIC_QUESTION_TYPES = {QuestionType.NUMBER, QuestionType.SCALE_5, QuestionType.SCALE_10}
    # Bounded walk guard for visibility_question ancestor-chain cycle checks.
    MAX_VISIBILITY_CHAIN_DEPTH = 50

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
        if self.visibility_question_id and self.visibility_question_id == self.pk:
            raise ValidationError({"visibility_question": "Una pregunta no puede depender de sí misma."})
        if self.visibility_question_id:
            self._check_visibility_chain_has_no_cycle()
        if self.visibility_option_id and self.visibility_option.question_id != self.visibility_question_id:
            raise ValidationError(
                {"visibility_option": "La opción debe pertenecer a la pregunta condicionante."}
            )
        if (
            self.visibility_operator in self.NUMERIC_VISIBILITY_OPERATORS
            and self.visibility_question_id
            and self.visibility_question.question_type not in self.NUMERIC_QUESTION_TYPES
        ):
            raise ValidationError(
                {
                    "visibility_operator": (
                        "Este operador solo aplica cuando la pregunta condicionante es numérica."
                    )
                }
            )

    def _check_visibility_chain_has_no_cycle(self):
        """Walk the visibility_question ancestor chain looking for a cycle.

        Direct self-reference (A depends on A) is already rejected above;
        this covers longer chains such as A -> B -> A. The walk is bounded
        so malformed/unexpected data can never hang validation.
        """
        node = self.visibility_question
        visited_ids = set()
        while node is not None:
            if self.pk is not None and node.pk == self.pk:
                raise ValidationError(
                    {"visibility_question": "La condición genera un ciclo entre preguntas."}
                )
            if node.pk in visited_ids:
                # Cycle among ancestors unrelated to self; stop walking
                # rather than looping forever.
                break
            visited_ids.add(node.pk)
            if len(visited_ids) > self.MAX_VISIBILITY_CHAIN_DEPTH:
                raise ValidationError(
                    {"visibility_question": "La cadena de preguntas condicionantes es demasiado larga."}
                )
            node = node.visibility_question


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
