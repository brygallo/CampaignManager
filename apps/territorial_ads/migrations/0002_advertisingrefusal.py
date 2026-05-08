from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('territorial_ads', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvertisingRefusal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('created_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='creado por')),
                ('modified_date', models.DateTimeField(auto_now=True, verbose_name='última fecha de modificación')),
                ('modified_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='modificado por')),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
                ('reason', models.TextField(help_text='Razón por la cual el propietario no acepta publicidad.', verbose_name='Motivo')),
                ('owner_reference', models.CharField(blank=True, help_text='Opcional: nombre o referencia para identificar de quién es la casa.', max_length=180, verbose_name='Referencia del propietario')),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)], verbose_name='Latitud')),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name='Longitud')),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='advertising_refusals', to='campaigns.campaign', verbose_name='Campaña')),
                ('reported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reported_advertising_refusals', to=settings.AUTH_USER_MODEL, verbose_name='Reportado por')),
            ],
            options={
                'verbose_name': 'Rechazo de publicidad',
                'verbose_name_plural': 'Rechazos de publicidad',
                'ordering': ['-created_date'],
            },
        ),
    ]
