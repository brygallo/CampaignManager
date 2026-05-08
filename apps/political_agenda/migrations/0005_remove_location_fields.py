from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("political_agenda", "0004_finalize_event_type_fk"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="politicalagendarequest",
            name="province",
        ),
        migrations.RemoveField(
            model_name="politicalagendarequest",
            name="canton",
        ),
        migrations.RemoveField(
            model_name="politicalagendarequest",
            name="parish",
        ),
        migrations.RemoveField(
            model_name="politicalagendarequest",
            name="sector",
        ),
        migrations.RemoveField(
            model_name="politicalagendaevent",
            name="province",
        ),
        migrations.RemoveField(
            model_name="politicalagendaevent",
            name="canton",
        ),
        migrations.RemoveField(
            model_name="politicalagendaevent",
            name="parish",
        ),
        migrations.RemoveField(
            model_name="politicalagendaevent",
            name="sector",
        ),
    ]
