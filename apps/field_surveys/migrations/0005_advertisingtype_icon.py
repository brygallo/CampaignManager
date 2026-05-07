from django.db import migrations, models


AD_TYPE_ICONS = {
    "AFICHE": "document",
    "STICKER": "sticker",
    "LONA": "picture",
    "BANNER": "tablet",
    "VALLA": "billboard",
    "OTRO": "element-12",
}


def populate_icons(apps, schema_editor):
    AdvertisingType = apps.get_model("field_surveys", "AdvertisingType")
    for code, icon in AD_TYPE_ICONS.items():
        AdvertisingType.objects.filter(code=code).update(icon=icon)


class Migration(migrations.Migration):

    dependencies = [
        ("field_surveys", "0004_alter_competitoradvertisingdetection_photo_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="advertisingtype",
            name="icon",
            field=models.CharField(
                default="element-12",
                help_text="Nombre del icono KeenIcons usado en mapas y vistas.",
                max_length=60,
                verbose_name="Icono",
            ),
        ),
        migrations.RunPython(populate_icons, migrations.RunPython.noop),
    ]
