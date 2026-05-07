from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('field_surveys', '0004_remove_fieldsurvey_address_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SurveySupportLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('created_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='creado por')),
                ('modified_date', models.DateTimeField(auto_now=True, verbose_name='última fecha de modificación')),
                ('modified_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='modificado por')),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
                ('code', models.CharField(max_length=40, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=120, verbose_name='Nombre')),
                ('color', models.CharField(blank=True, help_text='Hex #RRGGBB usado en mapas, dashboard y badges.', max_length=7, verbose_name='Color')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
            ],
            options={
                'verbose_name': 'Nivel de apoyo',
                'verbose_name_plural': 'Niveles de apoyo',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SurveyAdvertisingResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('created_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='creado por')),
                ('modified_date', models.DateTimeField(auto_now=True, verbose_name='última fecha de modificación')),
                ('modified_user', models.CharField(editable=False, max_length=128, null=True, verbose_name='modificado por')),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
                ('code', models.CharField(max_length=40, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=120, verbose_name='Nombre')),
                ('color', models.CharField(blank=True, help_text='Hex #RRGGBB usado en mapas, dashboard y badges.', max_length=7, verbose_name='Color')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Orden')),
            ],
            options={
                'verbose_name': 'Respuesta a publicidad',
                'verbose_name_plural': 'Respuestas a publicidad',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.RemoveField(
            model_name='fieldsurvey',
            name='results',
        ),
        migrations.DeleteModel(
            name='SurveyResultOption',
        ),
        migrations.AddField(
            model_name='fieldsurvey',
            name='support_level',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='field_surveys',
                to='field_surveys.surveysupportlevel',
                verbose_name='Nivel de apoyo',
            ),
        ),
        migrations.AddField(
            model_name='fieldsurvey',
            name='advertising_response',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='field_surveys',
                to='field_surveys.surveyadvertisingresponse',
                verbose_name='Respuesta a publicidad',
            ),
        ),
    ]
