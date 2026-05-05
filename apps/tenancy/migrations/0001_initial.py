import apps.tenancy.models
import django.db.models.deletion
import django_tenants.postgresql_backend.base
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "schema_name",
                    models.CharField(
                        db_index=True,
                        max_length=63,
                        unique=True,
                        validators=[django_tenants.postgresql_backend.base._check_schema_name],
                    ),
                ),
                ("name", models.CharField(max_length=200, verbose_name="Nombre del partido")),
                (
                    "slug",
                    models.SlugField(
                        help_text="Identificador URL-friendly (también usado como schema).",
                        max_length=80,
                        unique=True,
                        verbose_name="Slug",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Activo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
            ],
            options={
                "verbose_name": "Partido (tenant)",
                "verbose_name_plural": "Partidos (tenants)",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="TenantBranding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brand_name", models.CharField(blank=True, max_length=120, verbose_name="Nombre comercial")),
                (
                    "logo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=apps.tenancy.models.tenant_logo_upload_to,
                        verbose_name="Logo",
                    ),
                ),
                (
                    "favicon",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=apps.tenancy.models.tenant_favicon_upload_to,
                        verbose_name="Favicon",
                    ),
                ),
                (
                    "theme_default",
                    models.CharField(
                        choices=[("light", "Claro"), ("dark", "Oscuro"), ("system", "Sistema")],
                        default="light",
                        max_length=10,
                        verbose_name="Tema",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Actualizado")),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="branding",
                        to="tenancy.tenant",
                        verbose_name="Partido",
                    ),
                ),
            ],
            options={
                "verbose_name": "Branding",
                "verbose_name_plural": "Branding",
            },
        ),
        migrations.CreateModel(
            name="Domain",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(db_index=True, max_length=253, unique=True)),
                ("is_primary", models.BooleanField(db_index=True, default=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domains",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dominio",
                "verbose_name_plural": "Dominios",
            },
        ),
    ]
