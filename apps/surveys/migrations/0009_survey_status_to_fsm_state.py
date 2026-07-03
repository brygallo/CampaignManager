import apps.surveys.workflows
import django_fsm
from django.db import migrations


# Old CharField ``status`` value -> new FSMIntegerField ``state`` value.
STATUS_TO_STATE = {
    "draft": 1,
    "published": 2,
    "closed": 3,
    "archived": 4,
}


def forwards(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    for status, state in STATUS_TO_STATE.items():
        # ``.update()`` bypasses the protected FSM descriptor. Rows with an
        # unexpected status keep the ``state`` default (DRAFT).
        Survey.objects.filter(status=status).update(state=state)


def backwards(apps, schema_editor):
    Survey = apps.get_model("surveys", "Survey")
    for status, state in STATUS_TO_STATE.items():
        Survey.objects.filter(state=state).update(status=status)


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0008_question_type_extensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="survey",
            name="state",
            field=django_fsm.FSMIntegerField(
                choices=[
                    (1, "Borrador"),
                    (2, "Publicada"),
                    (3, "Cerrada"),
                    (4, "Archivada"),
                ],
                default=apps.surveys.workflows.SurveyWorkflow.Choices["DRAFT"],
                protected=True,
                verbose_name="Estado",
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="survey",
            name="status",
        ),
    ]
