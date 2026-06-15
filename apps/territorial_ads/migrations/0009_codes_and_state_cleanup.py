"""Data migration for the request/unit redesign cleanup:

- Requests no longer have Dañada(5)/Retirada(6): remap any such row to
  Instalada(4) — the real per-unit state already lives on each unit.
- Request codes move from the ``PF-`` prefix to ``SOL-`` (solicitud).
- Each physical unit gets its own ``PUB-`` code.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    PhysicalAdvertisement = apps.get_model("territorial_ads", "PhysicalAdvertisement")
    Unit = apps.get_model("territorial_ads", "PhysicalAdvertisementUnit")

    # ``.update()`` (not ``.save()``) so the tracing audit signal — which
    # needs a request user, absent in migrations — never fires.

    # Damage/retirement are unit-level now → collapse legacy request states.
    PhysicalAdvertisement.objects.filter(state__in=[5, 6]).update(state=4)

    # PF- → SOL- on request codes.
    for pk, code in PhysicalAdvertisement.objects.filter(
        code__startswith="PF-"
    ).values_list("pk", "code"):
        PhysicalAdvertisement.objects.filter(pk=pk).update(
            code="SOL-" + code[len("PF-"):]
        )

    # Give every unit its own PUB- code.
    for pk in Unit.objects.filter(code="").values_list("pk", flat=True):
        Unit.objects.filter(pk=pk).update(code=f"PUB-{pk:06d}")


def backwards(apps, schema_editor):
    PhysicalAdvertisement = apps.get_model("territorial_ads", "PhysicalAdvertisement")
    Unit = apps.get_model("territorial_ads", "PhysicalAdvertisementUnit")
    for pk, code in PhysicalAdvertisement.objects.filter(
        code__startswith="SOL-"
    ).values_list("pk", "code"):
        PhysicalAdvertisement.objects.filter(pk=pk).update(
            code="PF-" + code[len("SOL-"):]
        )
    Unit.objects.update(code="")


class Migration(migrations.Migration):
    dependencies = [
        ("territorial_ads", "0008_physicaladvertisementunit_code_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
