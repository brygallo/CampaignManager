"""Forms for the authentication app."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django_select2 import forms as s2forms
from superadmin.forms import ModelForm
from tracing.models import Rule

from .models import Profile, User


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Usuario o correo")

    error_messages = {
        "invalid_login": (
            "No pudimos validar el acceso al panel de campaña. "
            "Revisa el usuario/correo y la contraseña asignados."
        ),
        "inactive": "Esta cuenta está inactiva.",
    }

    def _resolve_tenant_label(self):
        """Identifies the active tenant so the error message can hint
        the user when they typed creds for the wrong subdomain."""
        if not self.request:
            return None
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return None
        # Prefer the human name; fall back to schema_name.
        return getattr(tenant, "name", None) or getattr(tenant, "schema_name", None)

    def get_invalid_login_error(self):
        tenant_label = self._resolve_tenant_label()
        message = self.error_messages["invalid_login"]
        if tenant_label:
            message = (
                f"{message} "
                f"Estás iniciando sesión en «{tenant_label}» — "
                f"si tu cuenta es de otro partido o cantón, abre el subdominio correcto."
            )
        return ValidationError(message, code="invalid_login")

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
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
        required=False,
        help_text="Déjalo en blanco para mantener la contraseña actual.",
    )
    is_active = forms.BooleanField(label="Activo", required=False, initial=True)
    is_staff = forms.BooleanField(label="Staff", required=False)
    is_superuser = forms.BooleanField(label="Superusuario", required=False)

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
            "groups": s2forms.ModelSelect2MultipleWidget(
                model="auth.Group",
                search_fields=["name__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Seleccione grupos...",
                },
            ),
            "user_permissions": s2forms.ModelSelect2MultipleWidget(
                model="auth.Permission",
                search_fields=[
                    "name__icontains",
                    "codename__icontains",
                    "content_type__app_label__icontains",
                    "content_type__model__icontains",
                ],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-placeholder": "Seleccione permisos...",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (self.instance and self.instance.pk):
            self.fields["password"].required = True
            self.fields["password"].help_text = "Define la contraseña inicial del usuario."
        # Snapshot the existing hash so save() can restore it when the admin
        # leaves the password blank — construct_instance() would otherwise
        # overwrite instance.password with the empty form value.
        self._original_password = (
            self.instance.password if self.instance and self.instance.pk else None
        )

    def clean_password(self):
        # Run the validators declared in AUTH_PASSWORD_VALIDATORS (length,
        # similarity, common, numeric). Skipped when the field is blank on
        # update, since blank means "keep the existing password".
        pwd = self.cleaned_data.get("password")
        if pwd:
            validate_password(pwd, user=self.instance or None)
        return pwd

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get("password")
        if pwd:
            user.set_password(pwd)
        elif self._original_password is not None:
            user.password = self._original_password
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


class MyProfileEditForm(forms.Form):
    """Self-service profile edit for the currently authenticated user.

    By default the form exposes the minimum descriptive fields a user can
    safely change on their own (``first_name``, ``last_name``, ``alias``,
    ``avatar``). When the user has the ``authentication.change_full_own_profile``
    permission, the form additionally exposes ``email``, ``phone_number`` and
    ``bio`` — useful for coordinators and admins who maintain their own
    extended contact info.

    Edits are persisted across two models (``User`` + ``Profile``) via a
    single ``save`` call so the view only deals with one form object.
    """

    _FULL_PROFILE_PERM = "authentication.change_full_own_profile"
    _USER_FIELDS_MINIMUM = ("first_name", "last_name", "alias")
    _USER_FIELDS_FULL = _USER_FIELDS_MINIMUM + ("email",)
    _PROFILE_FIELDS_FULL = ("phone_number", "bio")

    first_name = forms.CharField(label="Nombre", max_length=150, required=False)
    last_name = forms.CharField(label="Apellido", max_length=150, required=False)
    alias = forms.CharField(label="Alias", max_length=64, required=False)
    avatar = forms.ImageField(label="Avatar", required=False)
    clear_avatar = forms.BooleanField(
        label="Quitar avatar actual", required=False, initial=False,
    )
    email = forms.EmailField(label="Correo electrónico", required=False)
    phone_number = forms.CharField(label="Teléfono", max_length=20, required=False)
    bio = forms.CharField(
        label="Biografía",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.full_mode = bool(user and user.has_perm(self._FULL_PROFILE_PERM))
        if not self.full_mode:
            # Drop the elevated fields so they cannot be tampered with via
            # crafted POSTs (a non-privileged user sending ``email=...`` in
            # the body would otherwise hit ``cleaned_data`` and overwrite).
            for field_name in (*self._PROFILE_FIELDS_FULL, "email"):
                self.fields.pop(field_name, None)

        if not self.is_bound:
            self.initial.setdefault("first_name", user.first_name)
            self.initial.setdefault("last_name", user.last_name)
            self.initial.setdefault("alias", user.alias)
            profile = getattr(user, "profile", None)
            if profile is not None and self.fields.get("avatar"):
                self.fields["avatar"].help_text = (
                    "Subir reemplaza el avatar actual." if profile.avatar
                    else "Aún no has subido un avatar."
                )
            if self.full_mode:
                self.initial.setdefault("email", user.email)
                if profile is not None:
                    self.initial.setdefault("phone_number", profile.phone_number)
                    self.initial.setdefault("bio", profile.bio)

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip().lower()
        if not value:
            return self.user.email  # required at model level; keep current
        qs = self.user.__class__.objects.filter(email__iexact=value).exclude(pk=self.user.pk)
        if qs.exists():
            raise ValidationError("Ya existe un usuario con este correo.")
        return value

    def save(self):
        cleaned = self.cleaned_data
        user_fields = self._USER_FIELDS_FULL if self.full_mode else self._USER_FIELDS_MINIMUM
        update_fields = []
        for name in user_fields:
            if name in cleaned:
                setattr(self.user, name, cleaned.get(name, ""))
                update_fields.append(name)
        if update_fields:
            self.user.save(update_fields=update_fields)

        profile = self.user.profile
        profile_update = []
        if self.full_mode:
            for name in self._PROFILE_FIELDS_FULL:
                if name in cleaned:
                    setattr(profile, name, cleaned.get(name, ""))
                    profile_update.append(name)
        if cleaned.get("clear_avatar") and profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile_update.append("avatar")
        elif cleaned.get("avatar"):
            profile.avatar = cleaned["avatar"]
            profile_update.append("avatar")
        if profile_update:
            profile.save(update_fields=profile_update)
        return self.user


class GroupForm(ModelForm):
    class Meta:
        model = Group
        fieldsets = {
            "Datos del grupo": (
                ("name",),
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
