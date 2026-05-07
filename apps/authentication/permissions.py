"""Shared helpers for the permission matrix used across user/group form & detail.

The matrix groups every Permission by app_label -> model -> action so the
same template (`components/permissions_matrix.html`) can render it as either
editable checkboxes (form) or disabled checkboxes (detail).
"""
from django.apps import apps
from django.contrib.auth.models import Permission

# Standard CRUD action codes that get a dedicated column in the matrix.
STANDARD_PERM_ACTIONS = ("view", "add", "change", "delete")
STANDARD_PERM_LABELS = {
    "view": "Ver",
    "add": "Crear",
    "change": "Editar",
    "delete": "Eliminar",
}


def build_permission_matrix(direct_perm_ids, group_perm_map=None):
    """Group every Permission by app/model for the matrix template.

    ``direct_perm_ids``: iterable of Permission ids assigned directly to
    the holder (a User's ``user_permissions`` or a Group's ``permissions``).
    ``group_perm_map``: optional ``{permission_id: [group_name, ...]}`` to
    show inheritance markers; pass ``None`` when the holder is a Group.

    Returns a list of dicts ``{app_label, app_name, models}`` where each
    model contains ``{model_name, model_label, standard, custom}``.
    """
    direct_perm_ids = set(direct_perm_ids)
    group_perm_map = group_perm_map or {}

    permissions = (
        Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "codename"
        )
    )

    apps_map = {}
    for perm in permissions:
        ct = perm.content_type
        app_label = ct.app_label
        model_name = ct.model

        try:
            app_config = apps.get_app_config(app_label)
            app_name = str(app_config.verbose_name).capitalize()
        except LookupError:
            app_name = app_label

        model_class = ct.model_class()
        if model_class is not None:
            model_label = str(model_class._meta.verbose_name_plural).capitalize()
        else:
            model_label = model_name

        codename = perm.codename
        action = codename.split("_", 1)[0] if "_" in codename else codename
        is_standard = action in STANDARD_PERM_ACTIONS and codename == f"{action}_{model_name}"

        entry = {
            "id": perm.id,
            "codename": codename,
            "name": perm.name,
            "content_type_id": ct.id,
            "has_direct": perm.id in direct_perm_ids,
            "via_groups": group_perm_map.get(perm.id, []),
            "action": action,
        }

        app_dict = apps_map.setdefault(
            app_label,
            {"app_label": app_label, "app_name": app_name, "models": {}},
        )
        model_dict = app_dict["models"].setdefault(
            model_name,
            {
                "model_name": model_name,
                "model_label": model_label,
                "standard": {a: None for a in STANDARD_PERM_ACTIONS},
                "custom": [],
            },
        )
        if is_standard:
            model_dict["standard"][action] = entry
        else:
            model_dict["custom"].append(entry)

    apps_list = []
    for app_label in sorted(apps_map):
        a = apps_map[app_label]
        models_list = sorted(a["models"].values(), key=lambda m: m["model_label"])
        apps_list.append(
            {
                "app_label": a["app_label"],
                "app_name": a["app_name"],
                "models": models_list,
            }
        )
    return apps_list


def resolve_posted_permissions(post_data):
    """Translate ``perm_<codename>=<content_type_id>`` POST keys to a list of Permission.

    Permission codenames can collide across content types (e.g. a custom
    ``export`` permission in two apps), and Django's ``QueryDict[key]`` only
    returns the last value for repeated keys. Use ``getlist`` so every posted
    pair is captured, then resolve via the (codename, content_type_id) tuple.
    """
    prefix = "perm_"
    posted_pairs = set()
    getlist = getattr(post_data, "getlist", None)
    for key in post_data:
        if not key.startswith(prefix):
            continue
        codename = key[len(prefix):]
        values = getlist(key) if getlist else [post_data[key]]
        for value in values:
            posted_pairs.add((codename, str(value)))
    if not posted_pairs:
        return []
    codenames = [c for c, _ct in posted_pairs]
    candidates = Permission.objects.filter(codename__in=codenames).select_related("content_type")
    return [p for p in candidates if (p.codename, str(p.content_type_id)) in posted_pairs]


def build_user_permission_context(user, *, enabled):
    """Build the matrix context for a user (direct + inherited via groups)."""
    direct_ids = list(user.user_permissions.values_list("id", flat=True))
    group_perm_map = {}
    for group in user.groups.prefetch_related("permissions"):
        for perm in group.permissions.all():
            group_perm_map.setdefault(perm.id, []).append(group.name)
    return {
        "permission_groups": build_permission_matrix(direct_ids, group_perm_map),
        "standard_actions": STANDARD_PERM_ACTIONS,
        "standard_labels": STANDARD_PERM_LABELS,
        "permissions_matrix_enabled": enabled,
    }


def build_group_permission_context(group, *, enabled):
    """Build the matrix context for a group (only direct, no inheritance)."""
    direct_ids = list(group.permissions.values_list("id", flat=True)) if group else []
    return {
        "permission_groups": build_permission_matrix(direct_ids, group_perm_map=None),
        "standard_actions": STANDARD_PERM_ACTIONS,
        "standard_labels": STANDARD_PERM_LABELS,
        "permissions_matrix_enabled": enabled,
    }
