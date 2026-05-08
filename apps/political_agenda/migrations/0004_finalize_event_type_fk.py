"""Drop the legacy ``event_type`` CharField and promote ``event_type_fk`` to be
the canonical FK named ``event_type``.

Records without an ``event_type_fk`` after migration 0003 indicate stale data
that the data migration's "OTRO" fallback should have handled. The ALTER to
``null=False`` will fail loudly if any row is still empty.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("political_agenda", "0003_migrate_event_types"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="politicalagendarequest",
            name="event_type",
        ),
        migrations.RemoveField(
            model_name="politicalagendaevent",
            name="event_type",
        ),
        migrations.RenameField(
            model_name="politicalagendarequest",
            old_name="event_type_fk",
            new_name="event_type",
        ),
        migrations.RenameField(
            model_name="politicalagendaevent",
            old_name="event_type_fk",
            new_name="event_type",
        ),
        migrations.AlterField(
            model_name="politicalagendarequest",
            name="event_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="requests",
                to="political_agenda.agendaeventtype",
                verbose_name="Tipo",
            ),
        ),
        migrations.AlterField(
            model_name="politicalagendaevent",
            name="event_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="political_agenda.agendaeventtype",
                verbose_name="Tipo",
            ),
        ),
    ]
