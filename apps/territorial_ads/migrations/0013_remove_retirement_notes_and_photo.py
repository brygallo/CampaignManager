from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('territorial_ads', '0012_alter_physicaladvertisement_damage_photo_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='physicaladvertisement',
            name='retirement_notes',
        ),
        migrations.RemoveField(
            model_name='physicaladvertisement',
            name='retirement_photo',
        ),
    ]
