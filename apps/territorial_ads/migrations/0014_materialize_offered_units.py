from django.db import migrations


def materialize_units(apps, schema_editor):
    """Backfill physical units for requests whose items have fewer units than
    their quantity (units are now created at offer time, not at approval)."""
    PhysicalAdvertisementItem = apps.get_model(
        "territorial_ads", "PhysicalAdvertisementItem"
    )
    PhysicalAdvertisementUnit = apps.get_model(
        "territorial_ads", "PhysicalAdvertisementUnit"
    )
    PENDIENTE = 1  # PhysicalAdUnitWorkflow.PENDIENTE
    for item in PhysicalAdvertisementItem.objects.all():
        existing = set(
            item.units.values_list("unit_number", flat=True)
        )
        for number in range(1, item.quantity + 1):
            if number not in existing:
                unit = PhysicalAdvertisementUnit.objects.create(
                    item=item, unit_number=number, state=PENDIENTE
                )
                if not unit.code:
                    unit.code = f"PUB-{unit.pk:06d}"
                    unit.save(update_fields=["code"])


class Migration(migrations.Migration):

    dependencies = [
        ("territorial_ads", "0013_remove_physicaladvertisement_assigned_at_and_more"),
    ]

    operations = [
        migrations.RunPython(materialize_units, migrations.RunPython.noop),
    ]
