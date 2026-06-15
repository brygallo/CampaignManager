"""Materialize PhysicalAdvertisementUnit rows for pre-existing requests.

Requests that already passed approval (states PENDIENTE_INSTALACION and
beyond) get one unit per item/quantity. Unit state maps from the request
state; ad-level evidence (GPS, notes, installer, timestamps) is copied to
every unit as a best effort — legacy InstallationPhoto galleries stay on
the request.
"""
from django.db import migrations

# Request workflow values at the time of this migration.
REQ_PENDIENTE, REQ_INSTALADA, REQ_DANADA, REQ_RETIRADA = 3, 4, 5, 6
# Unit workflow values.
UNIT_RETIRADA, UNIT_PENDIENTE, UNIT_INSTALADA, UNIT_DANADA = 0, 1, 2, 3

REQUEST_TO_UNIT_STATE = {
    REQ_PENDIENTE: UNIT_PENDIENTE,
    REQ_INSTALADA: UNIT_INSTALADA,
    REQ_DANADA: UNIT_DANADA,
    REQ_RETIRADA: UNIT_RETIRADA,
}


def materialize_units(apps, schema_editor):
    PhysicalAdvertisement = apps.get_model("territorial_ads", "PhysicalAdvertisement")
    Unit = apps.get_model("territorial_ads", "PhysicalAdvertisementUnit")

    requests = PhysicalAdvertisement.objects.filter(
        state__in=list(REQUEST_TO_UNIT_STATE)
    ).prefetch_related("items")
    for ad in requests:
        unit_state = REQUEST_TO_UNIT_STATE[ad.state]
        installed = unit_state in (UNIT_INSTALADA, UNIT_DANADA, UNIT_RETIRADA)
        for item in ad.items.all():
            if Unit.objects.filter(item=item).exists():
                continue
            for number in range(1, item.quantity + 1):
                Unit.objects.create(
                    item=item,
                    unit_number=number,
                    state=unit_state,
                    latitude=ad.installed_latitude if installed else None,
                    longitude=ad.installed_longitude if installed else None,
                    notes=ad.installation_notes if installed else "",
                    installed_at=ad.installed_at if installed else None,
                    installed_by_id=ad.installed_by_id if installed else None,
                    damage_notes=ad.damage_notes if unit_state == UNIT_DANADA else "",
                    damage_reported_at=(
                        ad.damage_reported_at if unit_state == UNIT_DANADA else None
                    ),
                    damage_reported_by_id=(
                        ad.damage_reported_by_id if unit_state == UNIT_DANADA else None
                    ),
                    retired_at=ad.retired_at if unit_state == UNIT_RETIRADA else None,
                    retired_by_id=(
                        ad.retired_by_id if unit_state == UNIT_RETIRADA else None
                    ),
                )


def remove_units(apps, schema_editor):
    Unit = apps.get_model("territorial_ads", "PhysicalAdvertisementUnit")
    Unit.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("territorial_ads", "0006_advertisingtypesize_and_more"),
    ]

    operations = [
        migrations.RunPython(materialize_units, remove_units),
    ]
