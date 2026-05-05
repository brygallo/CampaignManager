import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("enable_campaigns", models.BooleanField(default=True, verbose_name="Campañas")),
                (
                    "enable_political_agenda",
                    models.BooleanField(default=True, verbose_name="Agenda política"),
                ),
                (
                    "enable_field_surveys",
                    models.BooleanField(default=True, verbose_name="Levantamientos de campo"),
                ),
                (
                    "enable_territorial_ads",
                    models.BooleanField(default=True, verbose_name="Publicidad territorial"),
                ),
                ("enable_locations", models.BooleanField(default=True, verbose_name="Geografía")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="settings",
                        to="tenancy.tenant",
                        verbose_name="Partido",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuración",
                "verbose_name_plural": "Configuraciones",
            },
        ),
    ]
