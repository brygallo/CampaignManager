"""Add AgendaEventType lookup model + GPS fields, plus a temporary FK on
Request and Event used by the data migration to backfill from the legacy
CharField. Migration 0004 swaps the temp FK into ``event_type``.
"""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("political_agenda", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgendaEventType",
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
                ("created_date", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("created_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="creado por")),
                ("modified_date", models.DateTimeField(auto_now=True, verbose_name="última fecha de modificación")),
                ("modified_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="modificado por")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="Código")),
                ("name", models.CharField(max_length=120, verbose_name="Nombre")),
                ("order", models.PositiveSmallIntegerField(default=0, verbose_name="Orden")),
                (
                    "color",
                    models.CharField(
                        default="#3e97ff",
                        help_text="Hex #RRGGBB usado en el calendario y badges.",
                        max_length=9,
                        verbose_name="Color",
                    ),
                ),
                (
                    "icon",
                    models.CharField(
                        default="calendar-tick",
                        help_text="Nombre del ícono Keenicons (sin el prefijo ki-).",
                        max_length=60,
                        verbose_name="Ícono",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tipo de evento",
                "verbose_name_plural": "Tipos de evento",
                "ordering": ["order", "name"],
            },
        ),
        migrations.AddField(
            model_name="politicalagendarequest",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(-90),
                    django.core.validators.MaxValueValidator(90),
                ],
                verbose_name="Latitud tentativa",
            ),
        ),
        migrations.AddField(
            model_name="politicalagendarequest",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(-180),
                    django.core.validators.MaxValueValidator(180),
                ],
                verbose_name="Longitud tentativa",
            ),
        ),
        migrations.AddField(
            model_name="politicalagendaevent",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(-90),
                    django.core.validators.MaxValueValidator(90),
                ],
                verbose_name="Latitud",
            ),
        ),
        migrations.AddField(
            model_name="politicalagendaevent",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(-180),
                    django.core.validators.MaxValueValidator(180),
                ],
                verbose_name="Longitud",
            ),
        ),
        migrations.AddField(
            model_name="politicalagendarequest",
            name="event_type_fk",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="requests",
                to="political_agenda.agendaeventtype",
                verbose_name="Tipo",
            ),
        ),
        migrations.AddField(
            model_name="politicalagendaevent",
            name="event_type_fk",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="political_agenda.agendaeventtype",
                verbose_name="Tipo",
            ),
        ),
    ]
