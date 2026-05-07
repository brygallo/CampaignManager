from django.db import migrations


# Some legacy rows have icon names that do not exist in the KeenIcons font
# bundled with the project (e.g. "billboard", "sticker"). Remap them to
# valid glyphs so the map markers actually render.
ICON_FIXES = {
    "billboard": "flag",
    "sticker": "tag",
}


def fix_icons(apps, schema_editor):
    AdvertisingType = apps.get_model("field_surveys", "AdvertisingType")
    for old, new in ICON_FIXES.items():
        AdvertisingType.objects.filter(icon=old).update(icon=new)


def revert_icons(apps, schema_editor):
    AdvertisingType = apps.get_model("field_surveys", "AdvertisingType")
    for old, new in ICON_FIXES.items():
        AdvertisingType.objects.filter(icon=new).update(icon=old)


class Migration(migrations.Migration):

    dependencies = [
        ("field_surveys", "0005_advertisingtype_icon"),
    ]

    operations = [
        migrations.RunPython(fix_icons, revert_icons),
    ]
