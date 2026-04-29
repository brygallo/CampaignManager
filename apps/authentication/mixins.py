"""Context helpers for authentication system views."""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q


class UserListMixin:
    """Match SIM behavior: staff can see all users; regular users see themselves."""

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
    """Expose direct and group-inherited user permissions to the detail template."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        user = self.get_object()
        direct_perms = set(user.user_permissions.select_related("content_type"))
        group_perm_map = {}

        for group in user.groups.prefetch_related("permissions").all():
            for perm in group.permissions.all():
                group_perm_map.setdefault(perm.id, []).append(group)

        permission_ids = {perm.id for perm in direct_perms} | set(group_perm_map)
        permissions = (
            Permission.objects.filter(id__in=permission_ids)
            .select_related("content_type")
            .order_by("content_type__app_label", "content_type__model", "name")
        )

        context.update(
            {
                "permissions_entries": [
                    {
                        "permission": perm,
                        "direct": perm in direct_perms,
                        "groups": group_perm_map.get(perm.id, []),
                        "app_name": self._get_app_name(perm),
                        "model_name": self._get_model_name(perm),
                    }
                    for perm in permissions
                ],
                "permissions_list_title": "Permisos del usuario",
                "permissions_list_empty": "Este usuario no tiene permisos asignados.",
                "show_permission_origin": True,
            }
        )
        return context

    def _get_app_name(self, permission):
        try:
            return str(apps.get_app_config(permission.content_type.app_label).verbose_name).capitalize()
        except LookupError:
            return permission.content_type.app_label

    def _get_model_name(self, permission):
        model_class = permission.content_type.model_class()
        if model_class:
            return str(model_class._meta.verbose_name_plural).capitalize()
        return permission.content_type.model


class GroupDetailMixin:
    """Add group permissions and assigned users to group detail."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        group = self.get_object()
        User = get_user_model()
        context.update(
            {
                "permissions_entries": [
                    {
                        "permission": perm,
                        "app_name": self._get_app_name(perm),
                        "model_name": self._get_model_name(perm),
                    }
                    for perm in group.permissions.select_related("content_type").order_by(
                        "content_type__app_label", "content_type__model", "name"
                    )
                ],
                "permissions_list_title": "Permisos del grupo",
                "permissions_list_empty": "Este grupo no tiene permisos asignados.",
                "users_list": User.objects.filter(groups=group)
                .select_related("profile")
                .order_by("-is_active", "first_name", "last_name", "username")
                .distinct(),
                "users_list_title": "Usuarios del grupo",
                "users_list_empty": "No hay usuarios asignados a este grupo.",
            }
        )
        return context

    def _get_app_name(self, permission):
        try:
            return str(apps.get_app_config(permission.content_type.app_label).verbose_name).capitalize()
        except LookupError:
            return permission.content_type.app_label

    def _get_model_name(self, permission):
        model_class = permission.content_type.model_class()
        if model_class:
            return str(model_class._meta.verbose_name_plural).capitalize()
        return permission.content_type.model


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
