from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.models import Campaign
from apps.locations.models import Canton, Parish, Province, Sector
from apps.political_agenda.transitions import (
    PoliticalAgendaEventTransitions,
    PoliticalAgendaRequestTransitions,
)
from apps.workflows.mixins import TransitionRequirementsMixin


class AgendaEventType(BaseModel):
    """Catálogo de tipos de evento (reunión, visita, mitin, ...).

    Color e ícono se usan al pintar los eventos en el calendario y en badges.
    """

    code = models.CharField("Código", max_length=40, unique=True)
    name = models.CharField("Nombre", max_length=120)
    order = models.PositiveSmallIntegerField("Orden", default=0)
    color = models.CharField(
        "Color",
        max_length=9,
        default="#3e97ff",
        help_text="Hex #RRGGBB usado en el calendario y badges.",
    )
    icon = models.CharField(
        "Ícono",
        max_length=60,
        default="calendar-tick",
        help_text="Nombre del ícono Keenicons (sin el prefijo ki-).",
    )

    class Meta:
        verbose_name = "Tipo de evento"
        verbose_name_plural = "Tipos de evento"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class PoliticalAgendaRequest(BaseModel, PoliticalAgendaRequestTransitions, TransitionRequirementsMixin):
    workflow = PoliticalAgendaRequestTransitions.workflow

    class Priority(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"
        URGENTE = "URGENTE", "Urgente"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="agenda_requests",
        verbose_name="Campaña",
    )
    title = models.CharField("Título", max_length=180)
    event_type = models.ForeignKey(
        AgendaEventType,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="Tipo",
    )
    state = FSMIntegerField(
        "Estado",
        choices=workflow.choices,
        default=workflow.PENDING,
        protected=True,
    )
    priority = models.CharField(
        "Prioridad", max_length=12, choices=Priority.choices, default=Priority.MEDIA
    )

    requester_name = models.CharField("Solicitante", max_length=180)
    requester_phone = models.CharField("Teléfono solicitante", max_length=32, blank=True)
    requester_email = models.EmailField("Correo solicitante", blank=True)
    organization = models.CharField("Organización / sector", max_length=180, blank=True)

    proposed_start_at = models.DateTimeField("Inicio tentativo", null=True, blank=True)
    proposed_end_at = models.DateTimeField("Fin tentativo", null=True, blank=True)
    alternative_dates = models.TextField("Fechas alternativas", blank=True)

    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="agenda_requests", verbose_name="Provincia", null=True, blank=True)
    canton = models.ForeignKey(Canton, on_delete=models.PROTECT, related_name="agenda_requests", verbose_name="Cantón", null=True, blank=True)
    parish = models.ForeignKey(Parish, on_delete=models.PROTECT, related_name="agenda_requests", verbose_name="Parroquia", null=True, blank=True)
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="agenda_requests", verbose_name="Sector / barrio", null=True, blank=True)
    address = models.CharField("Dirección", max_length=255, blank=True)
    reference = models.CharField("Referencia", max_length=255, blank=True)
    latitude = models.DecimalField(
        "Latitud tentativa",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "Longitud tentativa",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    objective = models.TextField("Objetivo", blank=True)
    expected_attendees = models.PositiveIntegerField("Asistentes esperados", default=0)
    notes = models.TextField("Notas", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_agenda_requests",
        verbose_name="Revisado por",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField("Fecha de revisión", null=True, blank=True)
    rejection_reason = models.TextField("Motivo de rechazo", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_agenda_requests",
        verbose_name="Creado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Solicitud de agenda política"
        verbose_name_plural = "Solicitudes de agenda política"
        ordering = ["-created_date"]
        permissions = (
            ("approve_politicalagendarequest", "Puede aprobar solicitudes de agenda política"),
            ("reject_politicalagendarequest", "Puede rechazar solicitudes de agenda política"),
        )

    def __str__(self):
        return f"{self.title} - {self.get_state_display()}"

    @property
    def blocks_candidate_agenda(self):
        return False

    def clean(self):
        errors = {}
        if self.proposed_start_at and self.proposed_end_at and self.proposed_end_at <= self.proposed_start_at:
            errors["proposed_end_at"] = "La fecha/hora fin debe ser posterior al inicio tentativo."
        if self.state == self.workflow.REJECTED and not self.rejection_reason:
            errors["rejection_reason"] = "Registra el motivo de rechazo."
        if errors:
            raise ValidationError(errors)

    @property
    def transition_requirements(self):
        if self.state in (self.workflow.PENDING, self.workflow.IN_REVIEW):
            return self.build_transition_requirements(
                "Aprobar",
                [
                    self.build_transition_requirement_item(
                        "Inicio tentativo", self.proposed_start_at, bool(self.proposed_start_at)
                    ),
                    self.build_transition_requirement_item(
                        "Fin tentativo", self.proposed_end_at, bool(self.proposed_end_at)
                    ),
                    self.build_transition_requirement_item(
                        "Solicitante", self.requester_name, bool(self.requester_name)
                    ),
                ],
                ready_text="Puedes aprobar o rechazar la solicitud desde el menú de acciones.",
            )
        if self.state == self.workflow.APPROVED:
            return self.build_transition_requirements(
                "Crear evento",
                [
                    self.build_transition_requirement_item(
                        "Solicitud aprobada", self.get_state_display(), True
                    )
                ],
                ready_text="Puedes generar el evento de agenda desde la solicitud aprobada.",
            )
        return None


class PoliticalAgendaEvent(BaseModel, PoliticalAgendaEventTransitions, TransitionRequirementsMixin):
    workflow = PoliticalAgendaEventTransitions.workflow

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="agenda_events",
        verbose_name="Campaña",
    )
    source_request = models.ForeignKey(
        PoliticalAgendaRequest,
        on_delete=models.SET_NULL,
        related_name="agenda_events",
        verbose_name="Solicitud origen",
        null=True,
        blank=True,
    )
    title = models.CharField("Título", max_length=180)
    event_type = models.ForeignKey(
        AgendaEventType,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name="Tipo",
    )
    state = FSMIntegerField(
        "Estado",
        choices=workflow.choices,
        default=workflow.DRAFT,
        protected=True,
    )
    start_at = models.DateTimeField("Inicio")
    end_at = models.DateTimeField("Fin")

    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="agenda_events", verbose_name="Provincia", null=True, blank=True)
    canton = models.ForeignKey(Canton, on_delete=models.PROTECT, related_name="agenda_events", verbose_name="Cantón", null=True, blank=True)
    parish = models.ForeignKey(Parish, on_delete=models.PROTECT, related_name="agenda_events", verbose_name="Parroquia", null=True, blank=True)
    sector = models.ForeignKey(Sector, on_delete=models.PROTECT, related_name="agenda_events", verbose_name="Sector / barrio", null=True, blank=True)
    address = models.CharField("Dirección", max_length=255, blank=True)
    reference = models.CharField("Referencia", max_length=255, blank=True)
    latitude = models.DecimalField(
        "Latitud",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "Longitud",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    organizer_name = models.CharField("Organizador / contacto", max_length=180, blank=True)
    organizer_phone = models.CharField("Teléfono contacto", max_length=32, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="responsible_agenda_events",
        verbose_name="Responsable",
        null=True,
        blank=True,
    )
    expected_attendees = models.PositiveIntegerField("Asistentes esperados", default=0)
    objective = models.TextField("Objetivo", blank=True)
    logistics_notes = models.TextField("Notas logísticas", blank=True)
    result_notes = models.TextField("Resultado / seguimiento", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_agenda_events",
        verbose_name="Creado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Evento de agenda política"
        verbose_name_plural = "Eventos de agenda política"
        ordering = ["start_at", "title"]
        permissions = (
            ("schedule_politicalagendaevent", "Puede agendar eventos políticos"),
        )

    def __str__(self):
        return f"{self.title} - {self.start_at:%d/%m/%Y %H:%M}"

    @property
    def blocks_candidate_agenda(self):
        return self.state == self.workflow.SCHEDULED

    def validate_agenda_rules(self, *, as_scheduled=False):
        errors = {}
        if self.end_at and self.start_at and self.end_at <= self.start_at:
            errors["end_at"] = "La fecha/hora fin debe ser posterior al inicio."
        if self.source_request_id:
            if self.source_request.state != PoliticalAgendaRequest.workflow.APPROVED:
                errors["source_request"] = "Solo puedes crear eventos desde solicitudes aprobadas."
            if self.campaign_id and self.source_request.campaign_id != self.campaign_id:
                errors["campaign"] = "La campaña debe coincidir con la solicitud origen."

        should_block = as_scheduled or self.state == self.workflow.SCHEDULED
        if (
            should_block
            and self.campaign_id
            and self.start_at
            and self.end_at
            and "end_at" not in errors
        ):
            candidate_id = self.campaign.candidate_id
            conflicts = PoliticalAgendaEvent.objects.filter(
                campaign__candidate_id=candidate_id,
                state=self.workflow.SCHEDULED,
                start_at__lt=self.end_at,
                end_at__gt=self.start_at,
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                errors["start_at"] = "Existe otro evento AGENDADO que cruza esta agenda del candidato."

        if errors:
            raise ValidationError(errors)

    @classmethod
    def build_from_request(cls, agenda_request, **overrides):
        data = {
            "campaign": agenda_request.campaign,
            "source_request": agenda_request,
            "title": agenda_request.title,
            "event_type": agenda_request.event_type,
            "start_at": agenda_request.proposed_start_at,
            "end_at": agenda_request.proposed_end_at,
            "province": agenda_request.province,
            "canton": agenda_request.canton,
            "parish": agenda_request.parish,
            "sector": agenda_request.sector,
            "address": agenda_request.address,
            "reference": agenda_request.reference,
            "latitude": agenda_request.latitude,
            "longitude": agenda_request.longitude,
            "organizer_name": agenda_request.requester_name,
            "organizer_phone": agenda_request.requester_phone,
            "expected_attendees": agenda_request.expected_attendees,
            "objective": agenda_request.objective,
        }
        data.update(overrides)
        return cls(**data)

    def clean(self):
        self.validate_agenda_rules()

    @property
    def transition_requirements(self):
        if self.state in (self.workflow.DRAFT, self.workflow.RESCHEDULED):
            return self.build_transition_requirements(
                "Agendar",
                [
                    self.build_transition_requirement_item(
                        "Inicio", self.start_at, bool(self.start_at)
                    ),
                    self.build_transition_requirement_item(
                        "Fin", self.end_at, bool(self.end_at)
                    ),
                    self.build_transition_requirement_item(
                        "Responsable", self.responsible, bool(self.responsible_id)
                    ),
                    self.build_transition_requirement_item(
                        "Dirección", self.address, bool(self.address)
                    ),
                ],
                help_text=(
                    "Completa los requisitos marcados en rojo y asegura que no haya cruces "
                    "con otras agendas del candidato antes de agendar."
                ),
            )
        if self.state == self.workflow.SCHEDULED:
            return self.build_transition_requirements(
                "Marcar realizado",
                [
                    self.build_transition_requirement_item(
                        "Resultado / seguimiento",
                        self.result_notes,
                        bool(self.result_notes),
                    )
                ],
                ready_text=(
                    "El evento está agendado. Registra el resultado y márcalo como realizado "
                    "una vez ejecutado."
                ),
            )
        return None
