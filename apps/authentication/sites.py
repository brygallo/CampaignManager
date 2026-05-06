"""Register models in superadmin."""
from django.contrib.auth.models import Group, Permission
from tracing.models import Trace

from superadmin.decorators import register

from core.base import BaseSite

from .forms import PermissionForm, RuleForm, UserForm
from .mixins import (
    GroupDetailMixin,
    PermissionUsersMixin,
    UserListMixin,
    UserPermissionsListMixin,
)
from .models import User


@register("authentication.User")
class UserSite(BaseSite):
    form_class = UserForm
    queryset = User.objects.select_related("profile").prefetch_related("groups")
    list_mixins = (UserListMixin,)
    detail_mixins = (UserPermissionsListMixin,)
    detail_template_name = "authentication/user_detail.html"
    slug_field = "username"
    list_fields = (
        "get_full_name:Nombre completo",
        "username",
        "email",
        "is_active:Activo",
    )
    detail_fields = {
        "Datos de acceso": (
            ("username", "email"),
        ),
        "Información personal": (
            ("first_name", "last_name"),
            ("alias",),
        ),
        "Permisos": (
            ("is_active", "is_staff", "is_superuser"),
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
    queryset = Group.objects.prefetch_related("permissions").order_by("name")
    detail_mixins = (GroupDetailMixin,)
    detail_template_name = "authentication/group_detail.html"
    fields = ("name", "permissions")
    list_fields = ("name",)
    detail_fields = ("name",)
    search_params = ("name__icontains",)


@register("auth.Permission")
class PermissionSite(BaseSite):
    form_class = PermissionForm
    queryset = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label",
        "content_type__model",
        "codename",
    )
    detail_mixins = (PermissionUsersMixin,)
    detail_template_name = "authentication/permission_detail.html"
    list_fields = ("name", "codename", "content_type:objeto")
    detail_fields = PermissionForm.Meta.fieldsets
    search_fields = (
        "name__icontains",
        "codename__icontains",
        "content_type__model__icontains",
        "content_type__app_label__icontains",
    )
    search_params = search_fields


@register("tracing.Trace")
class TraceSite(BaseSite):
    allow_views = ("list", "detail")
    queryset = Trace.objects.select_related("user", "content_type").order_by("-date")
    list_fields = ("name", "user", "date", "action", "ip")
    detail_fields = ("name", "user", "date", "action", "ip", "os", "message")
    filter_fields = ("action",)


@register("tracing.Rule")
class RuleSite(BaseSite):
    form_class = RuleForm
    list_fields = (
        "content_type",
        "check_create",
        "check_edit",
        "check_delete",
        "is_active",
    )
    detail_fields = RuleForm.Meta.fieldsets
    filter_fields = ("content_type", "is_active")
