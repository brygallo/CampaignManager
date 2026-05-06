from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("territorial_ads", "0005_physicaladvertisement_installation_instructions"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="physicaladvertisement",
            name="title",
        ),
    ]
