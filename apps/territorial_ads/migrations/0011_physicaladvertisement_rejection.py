from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('territorial_ads', '0010_physicaladvertisement_offered_photo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='physicaladvertisement',
            options={
                'ordering': ['-created_date'],
                'permissions': (
                    ('approve_physicaladvertisement', 'Puede aprobar publicidad física'),
                    ('reject_physicaladvertisement', 'Puede rechazar publicidad física'),
                    ('assign_physicaladvertisement', 'Puede asignar instalación de publicidad física'),
                    ('install_physicaladvertisement', 'Puede registrar instalación de publicidad física'),
                    ('report_damage_physicaladvertisement', 'Puede reportar daño de publicidad física'),
                    ('retire_physicaladvertisement', 'Puede retirar publicidad física'),
                ),
                'verbose_name': 'Publicidad física',
                'verbose_name_plural': 'Publicidad física',
            },
        ),
        migrations.AddField(
            model_name='physicaladvertisement',
            name='rejection_reason',
            field=models.TextField(blank=True, verbose_name='Motivo de rechazo'),
        ),
        migrations.AddField(
            model_name='physicaladvertisement',
            name='rejected_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de rechazo'),
        ),
        migrations.AddField(
            model_name='physicaladvertisement',
            name='rejected_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name='rejected_physical_ads',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Rechazado por',
            ),
        ),
    ]
