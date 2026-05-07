"""Catálogos base para publicidad territorial.

Pre-carga los tipos de costo (gratuita, pagada, donada, canje).

Uso:
    python manage.py tenant_command seed_territorial_ads_catalog --schema=<tenant>
"""
from django.core.management.base import BaseCommand

from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.models import AdvertisingCostType


COST_TYPES = [
    # (code, name, order, requires_amount)
    ("GRATUITA", "Gratuita", 10, False),
    ("PAGADA", "Pagada", 20, True),
    ("DONADA", "Donada", 30, False),
    ("CANJE", "Canje / permuta", 40, False),
]

AD_TYPES = [
    ("AFICHE", "Afiche", "document"),
    ("STICKER", "Sticker", "sticker"),
    ("LONA", "Lona", "picture"),
    ("BANNER", "Banner", "tablet"),
    ("VALLA", "Valla", "billboard"),
    ("OTRO", "Otro", "element-12"),
]


class Command(BaseCommand):
    help = "Crea los catálogos base de publicidad territorial."

    def handle(self, *args, **options):
        for order, (code, name, icon) in enumerate(AD_TYPES, start=10):
            obj, created = AdvertisingType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "icon": icon,
                    "order": order,
                    "is_active": True,
                },
            )
            self.stdout.write(
                f"AdvertisingType: {'Creado' if created else 'Actualizado'} {obj.code}"
            )

        for code, name, order, requires_amount in COST_TYPES:
            obj, created = AdvertisingCostType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "order": order,
                    "requires_amount": requires_amount,
                    "is_active": True,
                },
            )
            self.stdout.write(
                f"AdvertisingCostType: {'Creado' if created else 'Actualizado'} {obj.code}"
            )
