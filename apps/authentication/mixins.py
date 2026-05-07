"""Context helpers for authentication system views."""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .permissions import (
    build_group_permission_context,
    build_user_permission_context,
    resolve_posted_permissions,
)


class UserListMixin:
    """Staff users see all users; non-staff see only themselves."""

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("profile")
            .prefetch_related("groups")
            .order_by("-is_active", "first_name", "last_name", "username")
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(pk=self.request.user.pk)
        return queryset


class UserPermissionsListMixin:
    """Inject the read-only permission matrix into the user detail context."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update(build_user_permission_context(self.get_object(), enabled=False))
        return context


class GroupDetailMixin:
    """Inject the read-only permission matrix and member users into group detail."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        group = self.get_object()
        User = get_user_model()
        context.update(build_group_permission_context(group, enabled=False))
        context.update(
            {
                "users_list": User.objects.filter(groups=group)
                .select_related("profile")
                .order_by("-is_active", "first_name", "last_name", "username")
                .distinct(),
                "users_list_title": "Usuarios del grupo",
                "users_list_empty": "No hay usuarios asignados a este grupo.",
            }
        )
        return context


class RestrictPrivilegedFieldsMixin:
    """Prevent non-superusers from changing privileged fields on UserForm.

    Sets ``disabled=True`` on each privileged field, so Django ignores any
    submitted value and falls back to the instance's existing one — even if
    a malicious POST tries to inject ``is_superuser=True``.
    """

    PRIVILEGED_FIELDS = ("is_superuser", "is_staff", "groups", "user_permissions")

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        if not self.request.user.is_superuser:
            for name in self.PRIVILEGED_FIELDS:
                if name in form.fields:
                    form.fields[name].disabled = True
        return form


class GroupPermissionFormMixin:
    """Render the editable permission matrix on the GroupSite create/update form
    and persist `perm_<codename>` POST values onto Group.permissions."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        # During create the object doesn't exist yet -> empty selection.
        instance = getattr(self, "object", None)
        context.update(build_group_permission_context(instance, enabled=True))
        return context

    def form_valid(self, form):
        # Defer to the parent so SaveOptionsMixin's _continue/_addanother
        # handling and the standard redirect behavior keep working.
        response = super().form_valid(form)
        if self.object is not None:
            self.object.permissions.set(resolve_posted_permissions(self.request.POST))
        return response


class PermissionUsersMixin:
    """Add users who have the permission directly or through a group."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        permission = self.get_object()
        User = get_user_model()
        users = list(
            User.objects.filter(Q(user_permissions=permission) | Q(groups__permissions=permission))
            .select_related("profile")
            .prefetch_related("user_permissions", "groups__permissions")
            .order_by("-is_active", "first_name", "last_name", "username")
            .distinct()
        )
        for user in users:
            user.has_direct_permission = any(
                perm.id == permission.id for perm in user.user_permissions.all()
            )
            user.permission_groups = [
                group
                for group in user.groups.all()
                if any(perm.id == permission.id for perm in group.permissions.all())
            ]

        context.update(
            {
                "users_list": users,
                "users_list_title": "Usuarios con este permiso",
                "users_list_empty": "Ningún usuario tiene este permiso asignado.",
                "show_permission_source": True,
            }
        )
        return context
