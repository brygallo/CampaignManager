"""Registro de modelos en superadmin."""
from superadmin.decorators import register

from core.base import BaseSite

from .forms import UserForm


@register("authentication.User")
class UserSite(BaseSite):
    form_class = UserForm
    list_fields = (
        "username",
        "first_name:Nombre",
        "last_name:Apellido",
        "email",
        "is_active:Activo",
    )
    detail_fields = {
        "Datos de acceso": (
            ("username", "email"),
            ("is_active", "is_staff", "is_superuser"),
        ),
        "Información personal": (
            ("first_name", "last_name"),
            ("alias", "date_joined"),
        ),
    }
    search_params = (
        "username__icontains",
        "first_name__icontains",
        "last_name__icontains",
        "email__icontains",
    )
    filter_fields = ("is_active", "is_staff", "is_superuser")


@register("auth.Group")
class GroupSite(BaseSite):
    fields = ("name", "permissions")
    list_fields = ("name",)
    detail_fields = ("name", "permissions")
    search_params = ("name__icontains",)


@register("auth.Permission")
class PermissionSite(BaseSite):
    allow_views = ("list", "detail")
    list_fields = ("name", "codename", "content_type")
    search_params = ("name__icontains", "codename__icontains")


@register("tracing.Trace")
class TraceSite(BaseSite):
    allow_views = ("list", "detail")
    list_fields = ("name", "user", "date", "action", "ip")
    detail_fields = ("name", "user", "date", "action", "ip", "os", "message")
    filter_fields = ("action",)


@register("tracing.Rule")
class RuleSite(BaseSite):
    list_fields = (
        "content_type",
        "check_create",
        "check_edit",
        "check_delete",
        "is_active",
    )
    fields = ("content_type", "check_create", "check_edit", "check_delete", "is_active")
