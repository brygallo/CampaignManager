"""User custom + Profile."""
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

from core.fields import CompressedImageField


class User(AbstractUser):
    """Extended User with unique email and optional alias.

    USERNAME_FIELD remains `username` to preserve superadmin compatibility
    with ManagementForm, permissions, and related internals. Email is still
    validated as unique.
    """

    email = models.EmailField(
        "Correo electrónico",
        unique=True,
        error_messages={"unique": "Ya existe un usuario con este correo."},
    )
    alias = models.CharField("Alias", max_length=64, blank=True)

    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["last_name", "first_name", "username"]
        permissions = (
            ("view_profile", "Ver perfil de usuario"),
            (
                "change_full_own_profile",
                "Puede editar la configuración completa de su propio perfil "
                "(email, teléfono, biografía)",
            ),
        )

    def __str__(self):
        return self.get_full_name() or self.username

    def display_name(self):
        """Full name when available; otherwise the username, never blank."""
        return self.get_full_name() or self.username


class Profile(models.Model):
    """Extended OneToOne profile for User."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Usuario",
    )
    phone_number = models.CharField(
        "Teléfono",
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?\d{7,15}$",
                message="Número de teléfono inválido (7-15 dígitos, prefijo + opcional).",
            )
        ],
    )
    avatar = CompressedImageField(
        "Avatar",
        upload_to="avatars/",
        blank=True,
        null=True,
    )
    bio = models.TextField("Biografía", blank=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return f"Perfil de {self.user}"
