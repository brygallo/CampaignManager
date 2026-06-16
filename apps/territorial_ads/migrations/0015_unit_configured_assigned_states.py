import apps.territorial_ads.workflows
from django.db import migrations
from django.db.models import Q
import django_fsm


def reclassify_pending_units(apps, schema_editor):
    """Split the legacy PENDIENTE (1) bucket into the new CONFIGURADA (5) and
    ASIGNADA (6) states based on each unit's data.

    Bulk ``.update()`` is used so the FSMIntegerField ``protected`` guard is
    bypassed; never call ``.save()`` here, it would trip the FSM protection.
    ASIGNADA is applied first so a unit that is both configured and assigned
    lands on ASIGNADA.
    """
    PhysicalAdvertisementUnit = apps.get_model(
        "territorial_ads", "PhysicalAdvertisementUnit"
    )
    PENDIENTE = 1
    INSTALADA = 2  # noqa: F841 - documents the value space, not used directly
    CONFIGURADA = 5
    ASIGNADA = 6

    # Has an installer assigned -> ASIGNADA.
    PhysicalAdvertisementUnit.objects.filter(state=PENDIENTE).filter(
        Q(assigned_installer_id__isnull=False) | ~Q(installer_team="")
    ).update(state=ASIGNADA)

    # Still pending but configured -> CONFIGURADA.
    PhysicalAdvertisementUnit.objects.filter(state=PENDIENTE).filter(
        Q(size_id__isnull=False) | ~Q(installation_instructions="")
    ).update(state=CONFIGURADA)


class Migration(migrations.Migration):

    dependencies = [
        ("territorial_ads", "0014_materialize_offered_units"),
    ]

    operations = [
        migrations.AlterField(
            model_name="physicaladvertisementunit",
            name="state",
            field=django_fsm.FSMIntegerField(
                choices=[
                    (0, "Retirada"),
                    (1, "Por configurar"),
                    (5, "Configurada"),
                    (6, "Asignada"),
                    (2, "Instalada"),
                    (3, "Dañada"),
                    (4, "No instalada"),
                ],
                default=apps.territorial_ads.workflows.PhysicalAdUnitWorkflow.Choices[
                    "PENDIENTE"
                ],
                protected=True,
                verbose_name="Estado",
            ),
        ),
        migrations.RunPython(
            reclassify_pending_units, migrations.RunPython.noop
        ),
    ]
