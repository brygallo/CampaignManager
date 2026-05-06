from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("territorial_ads", "0003_location_fks"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="physicaladvertisement",
            name="province",
        ),
        migrations.RemoveField(
            model_name="physicaladvertisement",
            name="canton",
        ),
        migrations.RemoveField(
            model_name="physicaladvertisement",
            name="parish",
        ),
        migrations.RemoveField(
            model_name="physicaladvertisement",
            name="sector",
        ),
    ]
