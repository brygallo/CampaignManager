from django.db import models
from tracing.models import BaseModel


class Province(BaseModel):
    """Provincia (1er nivel territorial)."""

    code = models.CharField("Código", max_length=8, unique=True)
    name = models.CharField("Nombre", max_length=80, unique=True)

    class Meta:
        verbose_name = "Provincia"
        verbose_name_plural = "Provincias"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Canton(BaseModel):
    """Cantón (2do nivel territorial)."""

    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        related_name="cantons",
        verbose_name="Provincia",
    )
    code = models.CharField("Código", max_length=8, unique=True)
    name = models.CharField("Nombre", max_length=80)

    class Meta:
        verbose_name = "Cantón"
        verbose_name_plural = "Cantones"
        ordering = ["province__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["province", "name"], name="unique_canton_per_province"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.province.name})"


class Parish(BaseModel):
    """Parroquia (3er nivel territorial)."""

    class ParishKind(models.TextChoices):
        URBANA = "URBANA", "Urbana"
        RURAL = "RURAL", "Rural"

    canton = models.ForeignKey(
        Canton,
        on_delete=models.PROTECT,
        related_name="parishes",
        verbose_name="Cantón",
    )
    code = models.CharField("Código", max_length=10, unique=True)
    name = models.CharField("Nombre", max_length=120)
    kind = models.CharField(
        "Tipo",
        max_length=10,
        choices=ParishKind.choices,
        default=ParishKind.URBANA,
    )

    class Meta:
        verbose_name = "Parroquia"
        verbose_name_plural = "Parroquias"
        ordering = ["canton__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["canton", "name"], name="unique_parish_per_canton"
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.canton.name}"


class Sector(BaseModel):
    """Sector / barrio (4to nivel territorial)."""

    parish = models.ForeignKey(
        Parish,
        on_delete=models.PROTECT,
        related_name="sectors",
        verbose_name="Parroquia",
    )
    name = models.CharField("Nombre", max_length=160)

    class Meta:
        verbose_name = "Sector / Barrio"
        verbose_name_plural = "Sectores / Barrios"
        ordering = ["parish__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parish", "name"], name="unique_sector_per_parish"
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.parish.name}"
