from django.core.management.base import BaseCommand

from apps.field_surveys.models import (
    CompetitorAdvertisingType,
    OwnAdvertisingType,
    SurveyResultOption,
)


SURVEY_RESULTS = [
    ("NO_ATENDIO", "No atendió"),
    ("ATENDIO", "Atendió"),
    ("APOYA", "Apoya"),
    ("INDECISO", "Indeciso"),
    ("NO_APOYA", "No apoya"),
    ("ACEPTA_PUBLICIDAD", "Acepta publicidad"),
    ("RECHAZA_PUBLICIDAD", "Rechaza publicidad"),
    ("REQUIERE_SEGUIMIENTO", "Requiere seguimiento"),
]

OWN_AD_TYPES = [
    ("AFICHE", "Afiche"),
    ("STICKER", "Sticker"),
    ("LONA", "Lona"),
    ("BANNER", "Banner"),
    ("OTRO", "Otro"),
]

COMPETITOR_AD_TYPES = [
    ("AFICHE", "Afiche"),
    ("STICKER", "Sticker"),
    ("LONA", "Lona"),
    ("BANNER", "Banner"),
    ("VALLA", "Valla"),
    ("OTRO", "Otro"),
]


class Command(BaseCommand):
    help = "Crea los catálogos base de levantamiento de campo."

    def handle(self, *args, **options):
        self._seed(SurveyResultOption, SURVEY_RESULTS)
        self._seed(OwnAdvertisingType, OWN_AD_TYPES)
        self._seed(CompetitorAdvertisingType, COMPETITOR_AD_TYPES)

    def _seed(self, model, values):
        for order, (code, name) in enumerate(values, start=10):
            option, created = model.objects.update_or_create(
                code=code,
                defaults={"name": name, "order": order, "is_active": True},
            )
            self.stdout.write(f"{model._meta.verbose_name}: {'Creado' if created else 'Actualizado'} {option.code}")
