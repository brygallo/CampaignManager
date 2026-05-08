from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("political_agenda", "0005_remove_location_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="politicalagendarequest",
            name="requester_email",
        ),
    ]
