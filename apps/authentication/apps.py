from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"
    label = "authentication"
    verbose_name = "Autenticación"

    def ready(self):
        # Wire up post_save signal to auto-create Profile.
        from . import signals  # noqa: F401
