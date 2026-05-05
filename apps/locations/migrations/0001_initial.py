from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Province",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_date", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("created_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="creado por")),
                ("modified_date", models.DateTimeField(auto_now=True, verbose_name="última fecha de modificación")),
                ("modified_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="modificado por")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("code", models.CharField(max_length=8, unique=True, verbose_name="Código")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="Nombre")),
            ],
            options={
                "verbose_name": "Provincia",
                "verbose_name_plural": "Provincias",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Canton",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_date", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("created_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="creado por")),
                ("modified_date", models.DateTimeField(auto_now=True, verbose_name="última fecha de modificación")),
                ("modified_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="modificado por")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("code", models.CharField(max_length=8, unique=True, verbose_name="Código")),
                ("name", models.CharField(max_length=80, verbose_name="Nombre")),
                (
                    "province",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cantons",
                        to="locations.province",
                        verbose_name="Provincia",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cantón",
                "verbose_name_plural": "Cantones",
                "ordering": ["province__name", "name"],
            },
        ),
        migrations.CreateModel(
            name="Parish",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_date", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("created_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="creado por")),
                ("modified_date", models.DateTimeField(auto_now=True, verbose_name="última fecha de modificación")),
                ("modified_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="modificado por")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("code", models.CharField(max_length=10, unique=True, verbose_name="Código")),
                ("name", models.CharField(max_length=120, verbose_name="Nombre")),
                (
                    "kind",
                    models.CharField(
                        choices=[("URBANA", "Urbana"), ("RURAL", "Rural")],
                        default="URBANA",
                        max_length=10,
                        verbose_name="Tipo",
                    ),
                ),
                (
                    "canton",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="parishes",
                        to="locations.canton",
                        verbose_name="Cantón",
                    ),
                ),
            ],
            options={
                "verbose_name": "Parroquia",
                "verbose_name_plural": "Parroquias",
                "ordering": ["canton__name", "name"],
            },
        ),
        migrations.CreateModel(
            name="Sector",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_date", models.DateTimeField(auto_now_add=True, verbose_name="fecha de creación")),
                ("created_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="creado por")),
                ("modified_date", models.DateTimeField(auto_now=True, verbose_name="última fecha de modificación")),
                ("modified_user", models.CharField(editable=False, max_length=128, null=True, verbose_name="modificado por")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("name", models.CharField(max_length=160, verbose_name="Nombre")),
                (
                    "parish",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sectors",
                        to="locations.parish",
                        verbose_name="Parroquia",
                    ),
                ),
            ],
            options={
                "verbose_name": "Sector / Barrio",
                "verbose_name_plural": "Sectores / Barrios",
                "ordering": ["parish__name", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="canton",
            constraint=models.UniqueConstraint(
                fields=("province", "name"), name="unique_canton_per_province"
            ),
        ),
        migrations.AddConstraint(
            model_name="parish",
            constraint=models.UniqueConstraint(
                fields=("canton", "name"), name="unique_parish_per_canton"
            ),
        ),
        migrations.AddConstraint(
            model_name="sector",
            constraint=models.UniqueConstraint(
                fields=("parish", "name"), name="unique_sector_per_parish"
            ),
        ),
    ]
