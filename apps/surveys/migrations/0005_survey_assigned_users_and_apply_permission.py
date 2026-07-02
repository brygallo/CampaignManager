# Generated manually for survey respondent assignment fields.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("surveys", "0002_surveyquestion_visibility_operator_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="survey",
            options={
                "ordering": ["-created_date"],
                "permissions": (
                    ("publish_survey", "Puede publicar/cerrar encuestas"),
                    ("apply_all_surveys", "Puede responder todas las encuestas"),
                    ("view_survey_results", "Puede ver resultados de encuestas"),
                    ("export_survey_results", "Puede exportar resultados de encuestas"),
                ),
                "verbose_name": "Encuesta",
                "verbose_name_plural": "Encuestas",
            },
        ),
        migrations.AddField(
            model_name="survey",
            name="all_users_can_respond",
            field=models.BooleanField(
                default=False,
                help_text="Si está activo, cualquier usuario autenticado puede responder esta encuesta.",
                verbose_name="Todos los usuarios pueden responder",
            ),
        ),
        migrations.AddField(
            model_name="survey",
            name="assigned_users",
            field=models.ManyToManyField(
                blank=True,
                related_name="assigned_surveys",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Usuarios asignados",
            ),
        ),
    ]
