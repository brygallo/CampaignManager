from django.core.management.base import BaseCommand

from apps.field_surveys.models import (
    AdvertisingType,
    SurveyAdvertisingResponse,
    SurveySupportLevel,
)


SUPPORT_LEVELS = [
    # (code, name, color)
    ("APOYA", "Apoya", "#50cd89"),
    ("INDECISO", "Indeciso", "#ffc700"),
    ("NO_APOYA", "No apoya", "#f1416c"),
    ("NO_ATENDIO", "No atendió", "#7e8299"),
]

ADVERTISING_RESPONSES = [
    ("ACEPTA", "Acepta publicidad", "#3e97ff"),
    ("RECHAZA", "Rechaza publicidad", "#7e8299"),
]

AD_TYPES = [
    # (code, name, icon)
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
        self._seed_with_color(SurveySupportLevel, SUPPORT_LEVELS)
        self._seed_with_color(SurveyAdvertisingResponse, ADVERTISING_RESPONSES)
        self._seed_with_icon(AdvertisingType, AD_TYPES)

    def _seed_with_color(self, model, values):
        for order, (code, name, color) in enumerate(values, start=10):
            obj, created = model.objects.update_or_create(
                code=code,
                defaults={"name": name, "color": color, "order": order, "is_active": True},
            )
            self.stdout.write(
                f"{model._meta.verbose_name}: {'Creado' if created else 'Actualizado'} {obj.code}"
            )

    def _seed_with_icon(self, model, values):
        for order, (code, name, icon) in enumerate(values, start=10):
            obj, created = model.objects.update_or_create(
                code=code,
                defaults={"name": name, "icon": icon, "order": order, "is_active": True},
            )
            self.stdout.write(
                f"{model._meta.verbose_name}: {'Creado' if created else 'Actualizado'} {obj.code}"
            )
