from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('territorial_ads', '0007_physicaladvertisement_cost_amount_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvertisingCostType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('created_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='creado por')),
                ('modified_date', models.DateTimeField(auto_now=True, verbose_name='última fecha de modificación')),
                ('modified_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='modificado por')),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
                ('code', models.CharField(max_length=40, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=120, verbose_name='Nombre')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
                ('requires_amount', models.BooleanField(default=False, help_text='Si está activo, se exige capturar el monto acordado.', verbose_name='Requiere monto')),
            ],
            options={
                'verbose_name': 'Tipo de costo de publicidad',
                'verbose_name_plural': 'Tipos de costo de publicidad',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.AlterField(
            model_name='physicaladvertisement',
            name='cost_amount',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Sólo si el tipo de costo lo requiere.', max_digits=10, null=True, verbose_name='Monto acordado'),
        ),
        migrations.RemoveField(
            model_name='physicaladvertisement',
            name='cost_type',
        ),
        migrations.AddField(
            model_name='physicaladvertisement',
            name='cost_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='physical_advertisements', to='territorial_ads.advertisingcosttype', verbose_name='Tipo de costo'),
        ),
    ]
