from django.db import models
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.transitions import CampaignTransitions
from apps.workflows.mixins import TransitionRequirementsMixin
from core.fields import CompressedImageField


class Election(BaseModel):
    name = models.CharField("Nombre", max_length=128, unique=True)
    election_date = models.DateField("Fecha de elección", null=True, blank=True)
    description = models.TextField("Descripción", blank=True)

    class Meta:
        verbose_name = "Elección"
        verbose_name_plural = "Elecciones"
        ordering = ["-election_date", "name"]

    def __str__(self):
        return self.name


class PoliticalMovement(BaseModel):
    """Political movement or party."""

    name = models.CharField("Nombre", max_length=128, unique=True)
    acronym = models.CharField("Siglas", max_length=16, blank=True)
    list_number = models.CharField("Número de lista", max_length=8, blank=True)
    color = models.CharField("Color", max_length=7, blank=True, help_text="Hex #RRGGBB")
    logo = CompressedImageField("Logo", upload_to="movements/logos/", null=True, blank=True)

    class Meta:
        verbose_name = "Movimiento político"
        verbose_name_plural = "Movimientos políticos"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}{f' ({self.acronym})' if self.acronym else ''}"


class Position(BaseModel):
    """Target office or role, such as mayor, council member, or prefect."""

    name = models.CharField("Cargo", max_length=128, unique=True)
    scope = models.CharField(
        "Ámbito",
        max_length=32,
        choices=[
            ("nacional", "Nacional"),
            ("provincial", "Provincial"),
            ("cantonal", "Cantonal"),
            ("parroquial", "Parroquial"),
        ],
        blank=True,
    )

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Candidate(BaseModel):
    """Candidate person."""

    full_name = models.CharField("Nombre completo", max_length=180)
    identification = models.CharField(
        "Cédula", max_length=20, unique=True, null=True, blank=True
    )
    email = models.EmailField("Correo", blank=True)
    phone = models.CharField("Teléfono", max_length=32, blank=True)
    photo = CompressedImageField("Foto", upload_to="candidates/photos/", null=True, blank=True)
    bio = models.TextField("Biografía", blank=True)

    class Meta:
        verbose_name = "Candidato"
        verbose_name_plural = "Candidatos"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Campaign(BaseModel, CampaignTransitions, TransitionRequirementsMixin):
    """Election campaign."""

    workflow = CampaignTransitions.workflow

    name = models.CharField("Nombre", max_length=180)
    election = models.ForeignKey(
        Election, on_delete=models.PROTECT,
        related_name="campaigns", verbose_name="Elección",
    )
    candidate = models.ForeignKey(
        Candidate, on_delete=models.PROTECT,
        related_name="campaigns", verbose_name="Candidato",
    )
    movement = models.ForeignKey(
        PoliticalMovement, on_delete=models.PROTECT,
        related_name="campaigns", verbose_name="Movimiento",
    )
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT,
        related_name="campaigns", verbose_name="Cargo",
    )
    start_date = models.DateField("Inicio", null=True, blank=True)
    end_date = models.DateField("Fin", null=True, blank=True)
    description = models.TextField("Descripción", blank=True)

    state = FSMIntegerField(
        "Estado",
        choices=workflow.choices,
        default=workflow.DRAFT,
        protected=True,
    )

    class Meta:
        verbose_name = "Campaña electoral"
        verbose_name_plural = "Campañas electorales"
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["election", "candidate", "position"],
                name="campaigns_unique_election_candidate_position",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.candidate}"

    def get_active_dependencies(self):
        """Return counts of dependent records that block close/cancel.

        Scheduled events block the candidate agenda; ads in intermediate
        states remain active in the territory.
        """
        from apps.political_agenda.models import PoliticalAgendaEvent
        from apps.territorial_ads.models import PhysicalAdvertisement

        scheduled_events = PoliticalAgendaEvent.objects.filter(
            campaign_id=self.pk,
            state=PoliticalAgendaEvent.workflow.SCHEDULED,
        ).count()
        active_ads = PhysicalAdvertisement.objects.filter(
            campaign_id=self.pk,
            state__in=[
                PhysicalAdvertisement.workflow.OFRECIDA,
                PhysicalAdvertisement.workflow.APROBADA,
                PhysicalAdvertisement.workflow.PENDIENTE_INSTALACION,
                PhysicalAdvertisement.workflow.INSTALADA,
                PhysicalAdvertisement.workflow.DANADA,
            ],
        ).count()
        return {
            "scheduled_events": scheduled_events,
            "active_ads": active_ads,
        }

    @property
    def transition_requirements(self):
        if self.state == self.workflow.DRAFT:
            return self.build_transition_requirements(
                "Activar campaña",
                [
                    self.build_transition_requirement_item(
                        "Inicio", self.start_date, bool(self.start_date)
                    ),
                    self.build_transition_requirement_item(
                        "Fin", self.end_date, bool(self.end_date)
                    ),
                ],
                ready_text="Puedes activar la campaña desde el menú de acciones.",
            )
        if self.state == self.workflow.ACTIVE:
            deps = self.get_active_dependencies()
            return self.build_transition_requirements(
                "Cerrar campaña",
                [
                    self.build_transition_requirement_item(
                        "Sin eventos AGENDADOS pendientes",
                        f"{deps['scheduled_events']} agendados",
                        deps["scheduled_events"] == 0,
                    ),
                    self.build_transition_requirement_item(
                        "Sin publicidad activa",
                        f"{deps['active_ads']} en territorio",
                        deps["active_ads"] == 0,
                    ),
                ],
                help_text=(
                    "Antes de cerrar, marca como realizados o cancela los eventos agendados y "
                    "retira o cancela las publicidades activas."
                ),
                ready_text="Puedes cerrar la campaña desde el menú de acciones.",
            )
        return None
