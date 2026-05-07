from django.db import migrations, models
import django.db.models.deletion


AD_TYPES = [
    ("AFICHE", "Afiche", "document", 10),
    ("STICKER", "Sticker", "sticker", 20),
    ("LONA", "Lona", "picture", 30),
    ("BANNER", "Banner", "tablet", 40),
    ("VALLA", "Valla", "billboard", 50),
    ("OTRO", "Otro", "element-12", 60),
]


def seed_types(apps, schema_editor):
    AdvertisingType = apps.get_model("field_surveys", "AdvertisingType")
    for code, name, icon, order in AD_TYPES:
        AdvertisingType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "icon": icon,
                "order": order,
                "is_active": True,
            },
        )


def migrate_type_values(apps, schema_editor):
    PhysicalAdvertisement = apps.get_model("territorial_ads", "PhysicalAdvertisement")
    AdvertisingType = apps.get_model("field_surveys", "AdvertisingType")
    by_code = {item.code: item.pk for item in AdvertisingType.objects.all()}
    old_to_code = {
        "afiche": "AFICHE",
        "lona": "LONA",
        "valla": "VALLA",
        "otro": "OTRO",
    }
    fallback = by_code.get("AFICHE") or by_code.get("OTRO")
    for ad in PhysicalAdvertisement.objects.all().only("pk", "advertisement_type"):
        code = old_to_code.get((ad.advertisement_type or "").lower())
        ad.advertisement_type_fk_id = by_code.get(code) or fallback
        ad.save(update_fields=["advertisement_type_fk"])


class Migration(migrations.Migration):

    dependencies = [
        ("field_surveys", "0005_advertisingtype_icon"),
        ("territorial_ads", "0013_remove_retirement_notes_and_photo"),
    ]

    operations = [
        migrations.RunPython(seed_types, migrations.RunPython.noop),
        migrations.AddField(
            model_name="physicaladvertisement",
            name="advertisement_type_fk",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="physical_advertisements",
                to="field_surveys.advertisingtype",
                verbose_name="Tipo de publicidad",
            ),
        ),
        migrations.RunPython(migrate_type_values, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="physicaladvertisement",
            name="advertisement_type",
        ),
        migrations.RenameField(
            model_name="physicaladvertisement",
            old_name="advertisement_type_fk",
            new_name="advertisement_type",
        ),
        migrations.AlterField(
            model_name="physicaladvertisement",
            name="advertisement_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="physical_advertisements",
                to="field_surveys.advertisingtype",
                verbose_name="Tipo de publicidad",
            ),
        ),
        migrations.AlterModelOptions(
            name="physicaladvertisement",
            options={
                "ordering": ["-created_date"],
                "permissions": (
                    ("approve_physicaladvertisement", "Puede aprobar publicidad"),
                    ("reject_physicaladvertisement", "Puede rechazar publicidad"),
                    ("assign_physicaladvertisement", "Puede asignar instalación de publicidad"),
                    ("install_physicaladvertisement", "Puede registrar instalación de publicidad"),
                    ("report_damage_physicaladvertisement", "Puede reportar daño de publicidad"),
                    ("retire_physicaladvertisement", "Puede retirar publicidad"),
                ),
                "verbose_name": "Publicidad",
                "verbose_name_plural": "Publicidad",
            },
        ),
    ]
