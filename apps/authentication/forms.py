"""Formularios de la app authentication."""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Permission
from django_select2 import forms as s2forms
from superadmin.forms import ModelForm
from tracing.models import Rule

from .models import Profile, User


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Usuario o correo institucional")

    error_messages = {
        "invalid_login": (
            "No pudimos validar el acceso al panel de campaña. "
            "Revisa el usuario/correo y la contraseña asignados."
        ),
        "inactive": "Esta cuenta está inactiva.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip()

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


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


class PermissionForm(ModelForm):
    class Meta:
        model = Permission
        fieldsets = {
            "Permiso": (
                ("name", "codename"),
                ("content_type",),
            ),
        }
        widgets = {
            "content_type": s2forms.ModelSelect2Widget(
                model="contenttypes.contenttype",
                search_fields=["app_label__icontains", "model__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0},
            ),
        }


class UserPermissionForm(ModelForm):
    class Meta:
        model = User
        fields = ("groups",)
        widgets = {
            "groups": s2forms.ModelSelect2MultipleWidget(
                model="auth.Group",
                search_fields=["name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].label = "Grupos del usuario"


class RuleForm(ModelForm):
    class Meta:
        model = Rule
        fieldsets = (
            "content_type",
            ("check_create", "check_edit", "check_delete"),
            "is_active",
        )
        widgets = {
            "content_type": s2forms.ModelSelect2Widget(
                model="contenttypes.contenttype",
                search_fields=["app_label__icontains", "model__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0},
            ),
        }
