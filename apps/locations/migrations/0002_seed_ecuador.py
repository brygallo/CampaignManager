from django.db import migrations

from apps.locations.data import ECUADOR


def seed_ecuador(apps, schema_editor):
    Province = apps.get_model("locations", "Province")
    Canton = apps.get_model("locations", "Canton")
    Parish = apps.get_model("locations", "Parish")

    for province_code, province_name, cantons in ECUADOR:
        province, _ = Province.objects.update_or_create(
            code=province_code, defaults={"name": province_name}
        )
        for canton_code, canton_name, parishes in cantons:
            canton, _ = Canton.objects.update_or_create(
                code=canton_code,
                defaults={"name": canton_name, "province": province},
            )
            for parish_code, parish_name, parish_kind in parishes:
                if Parish.objects.filter(canton=canton, name=parish_name).exclude(
                    code=parish_code
                ).exists():
                    continue
                Parish.objects.update_or_create(
                    code=parish_code,
                    defaults={
                        "name": parish_name,
                        "canton": canton,
                        "kind": parish_kind,
                    },
                )


def unseed_ecuador(apps, schema_editor):
    apps.get_model("locations", "Parish").objects.all().delete()
    apps.get_model("locations", "Canton").objects.all().delete()
    apps.get_model("locations", "Province").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("locations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_ecuador, unseed_ecuador),
    ]
