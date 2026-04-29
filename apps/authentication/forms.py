"""Formularios de la app authentication."""
from django import forms
from django.contrib.auth.forms import UserChangeForm
from superadmin.forms import ModelForm

from .models import Profile, User


class UserForm(ModelForm):
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Déjalo en blanco para mantener la contraseña actual.",
    )

    class Meta:
        model = User
        fieldsets = {
            "Datos de acceso": (
                ("username", "email"),
                ("password",),
            ),
            "Información personal": (
                ("first_name", "last_name"),
                ("alias",),
            ),
            "Permisos": (
                ("is_active", "is_staff", "is_superuser"),
                ("groups", "user_permissions"),
            ),
        }
        widgets = {
            "groups": forms.SelectMultiple(attrs={"class": "form-select"}),
            "user_permissions": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get("password")
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
            self.save_m2m()
        return user


class ProfileForm(ModelForm):
    class Meta:
        model = Profile
        fieldsets = {
            "Perfil": (
                ("phone_number", "avatar"),
                ("bio",),
            ),
        }
