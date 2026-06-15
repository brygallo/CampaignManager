"""Re-derive request state for places whose every unit is already retired.

After migration 0009 collapsed the legacy Dañada/Retirada request states to
Instalada, some requests are Instalada but all their (non-discarded) units
are Retirada. The request state is now derived from units, so bring those
back to Retirada(5).
"""
from django.db import migrations

REQ_INSTALADA, REQ_RETIRADA = 4, 5
UNIT_RETIRADA, UNIT_DESCARTADA = 0, 4


def forwards(apps, schema_editor):
    PhysicalAdvertisement = apps.get_model("territorial_ads", "PhysicalAdvertisement")
    Unit = apps.get_model("territorial_ads", "PhysicalAdvertisementUnit")

    for ad_id in PhysicalAdvertisement.objects.filter(
        state=REQ_INSTALADA
    ).values_list("pk", flat=True):
        states = list(
            Unit.objects.filter(item__advertisement_id=ad_id).values_list(
                "state", flat=True
            )
        )
        active = [s for s in states if s != UNIT_DESCARTADA]
        if active and all(s == UNIT_RETIRADA for s in active):
            PhysicalAdvertisement.objects.filter(pk=ad_id).update(state=REQ_RETIRADA)


def backwards(apps, schema_editor):
    PhysicalAdvertisement = apps.get_model("territorial_ads", "PhysicalAdvertisement")
    PhysicalAdvertisement.objects.filter(state=REQ_RETIRADA).update(state=REQ_INSTALADA)


class Migration(migrations.Migration):
    dependencies = [
        ("territorial_ads", "0010_alter_physicaladvertisement_state"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
