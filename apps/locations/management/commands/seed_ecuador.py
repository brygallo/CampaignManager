"""Carga la jerarquía territorial de Ecuador (provincias, cantones, parroquias).

Reemplaza la data-migration legacy `0002_seed_ecuador` que vivía en
`apps/locations/migrations/`. Se mantiene como comando explícito para que el
catálogo se siembre por tenant según se necesite.

Uso:
    python manage.py tenant_command seed_ecuador --schema=<tenant>
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.locations.data import ECUADOR
from apps.locations.models import Canton, Parish, Province


class Command(BaseCommand):
    help = "Carga provincias, cantones y parroquias de Ecuador."

    @transaction.atomic
    def handle(self, *args, **opts):
        provinces = cantons = parishes = 0
        for province_code, province_name, canton_list in ECUADOR:
            province, _ = Province.objects.update_or_create(
                code=province_code, defaults={"name": province_name}
            )
            provinces += 1
            for canton_code, canton_name, parish_list in canton_list:
                canton, _ = Canton.objects.update_or_create(
                    code=canton_code,
                    defaults={"name": canton_name, "province": province},
                )
                cantons += 1
                for parish_code, parish_name, parish_kind in parish_list:
                    if Parish.objects.filter(canton=canton, name=parish_name).exclude(
                        code=parish_code
                    ).exists():
                        continue
                    Parish.objects.update_or_create(
                        code=parish_code,
                        defaults={
                            "name": parish_name,
                            "canton": canton,
                            "kind": parish_kind,
                        },
                    )
                    parishes += 1

        self.stdout.write(self.style.SUCCESS(
            f"✔ Ecuador sembrado: {provinces} provincias, {cantons} cantones, {parishes} parroquias."
        ))
