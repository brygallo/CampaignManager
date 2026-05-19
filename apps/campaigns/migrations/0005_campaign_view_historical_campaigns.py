from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0004_campaign_is_default_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="campaign",
            options={
                "ordering": ["-created_date"],
                "permissions": (
                    ("view_historical_campaigns", "Puede ver campañas históricas e inactivas"),
                ),
                "verbose_name": "Campaña electoral",
                "verbose_name_plural": "Campañas electorales",
            },
        ),
    ]
