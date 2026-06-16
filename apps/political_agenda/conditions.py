"""Permission/visibility check functions for political agenda.

Module-level functions, like the ``conditions.py`` of sim's apps. Each takes a
model/user instance and returns a ``bool``. ``can_view_private_events`` is the
single source of truth for the private-event visibility rule, shared by the
calendar views and the admin site querysets (previously duplicated in both).
"""
from apps.political_agenda.constants import VIEW_PRIVATE_EVENT_PERM


def can_view_private_events(user):
    """User can see private events if active and superuser or holds the perm."""
    return bool(
        user
        and user.is_active
        and (user.is_superuser or user.has_perm(VIEW_PRIVATE_EVENT_PERM))
    )
