"""Modelos para campañas electorales.

`Campaign` es el modelo principal. Se relaciona con catálogos de:
  - `Election`            (Elección — proceso electoral, p.ej. "Seccionales 2027")
  - `Candidate`           (Candidato)
  - `PoliticalMovement`   (Movimiento político / partido)
  - `Position`            (Cargo al que aspira)

El campo `state` es un FSM (django-fsm) cuyo workflow se define en
`apps.campaigns.workflows.CampaignWorkflow` y cuyas transiciones viven
en `apps.campaigns.transitions.CampaignTransitions` (patrón sim).
"""
from django.db import models
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.transitions import CampaignTransitions


# ---------- Catálogos ----------

class Election(BaseModel):
    """Proceso electoral (p.ej. "Elecciones Seccionales 2027")."""

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
    """Movimiento político o partido."""

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
    """Cargo / dignidad al que se aspira (Alcalde, Concejal, Prefecto, ...)."""

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
    """Persona candidata."""

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


# ---------- Campaña electoral ----------

class Campaign(BaseModel, CampaignTransitions):
    """Campaña electoral."""

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
