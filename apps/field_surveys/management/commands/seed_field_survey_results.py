from django.core.management.base import BaseCommand

from apps.field_surveys.models import (
    AdvertisingType,
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

AD_TYPES = [
    ("AFICHE", "Afiche", "document"),
    ("STICKER", "Sticker", "tag"),
    ("LONA", "Lona", "picture"),
    ("BANNER", "Banner", "tablet"),
    ("VALLA", "Valla", "flag"),
    ("OTRO", "Otro", "element-12"),
]


class Command(BaseCommand):
    help = "Crea los catálogos base de levantamiento de campo."

    def handle(self, *args, **options):
        self._seed(SurveyResultOption, SURVEY_RESULTS)
        self._seed(AdvertisingType, AD_TYPES)

    def _seed(self, model, values):
        for order, value in enumerate(values, start=10):
            code, name, *extra = value
            defaults = {"name": name, "order": order, "is_active": True}
            if extra:
                defaults["icon"] = extra[0]
            option, created = model.objects.update_or_create(
                code=code,
                defaults=defaults,
            )
            self.stdout.write(f"{model._meta.verbose_name}: {'Creado' if created else 'Actualizado'} {option.code}")
