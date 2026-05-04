from django.db import models
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.transitions import CampaignTransitions


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
    logo = models.ImageField("Logo", upload_to="movements/logos/", null=True, blank=True)

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
    photo = models.ImageField("Foto", upload_to="candidates/photos/", null=True, blank=True)
    bio = models.TextField("Biografía", blank=True)

    class Meta:
        verbose_name = "Candidato"
        verbose_name_plural = "Candidatos"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Campaign(BaseModel, CampaignTransitions):
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
