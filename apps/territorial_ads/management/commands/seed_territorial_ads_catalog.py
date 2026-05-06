"""Catálogos base para publicidad territorial.

Pre-carga los tipos de costo (gratuita, pagada, donada, canje).

Uso:
    python manage.py tenant_command seed_territorial_ads_catalog --schema=<tenant>
"""
from django.core.management.base import BaseCommand

from apps.territorial_ads.models import AdvertisingCostType


COST_TYPES = [
    # (code, name, order, requires_amount)
    ("GRATUITA", "Gratuita", 10, False),
    ("PAGADA", "Pagada", 20, True),
    ("DONADA", "Donada", 30, False),
    ("CANJE", "Canje / permuta", 40, False),
]


class Command(BaseCommand):
    help = "Crea los catálogos base de publicidad territorial."

    def handle(self, *args, **options):
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
