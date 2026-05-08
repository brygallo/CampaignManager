from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("political_agenda", "0006_remove_requester_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="politicalagendaevent",
            name="is_public",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si está marcado, cualquier usuario con acceso al módulo verá el evento. "
                    "Si se desmarca, solo los usuarios con el permiso «Puede ver eventos privados» "
                    "podrán verlo en el listado y el calendario."
                ),
                verbose_name="Visible al público",
            ),
        ),
        migrations.AlterModelOptions(
            name="politicalagendaevent",
            options={
                "ordering": ["start_at", "title"],
                "permissions": (
                    ("schedule_politicalagendaevent", "Puede agendar eventos políticos"),
                    ("view_private_politicalagendaevent", "Puede ver eventos privados"),
                ),
                "verbose_name": "Evento de agenda política",
                "verbose_name_plural": "Eventos de agenda política",
            },
        ),
    ]
