"""Soft multi-site: middleware and helpers for the active Site in session."""
from typing import Optional

SITE_SESSION_KEY = "active_site_id"


def get_active_site(request) -> Optional["apps.sites_mgmt.models.Site"]:  # noqa: F821
    """Return the active Site stored in session, or the user's first one."""
    if not getattr(request, "session", None):
        return None

    site_id = request.session.get(SITE_SESSION_KEY)

    if not site_id and getattr(request, "user", None) and request.user.is_authenticated:
        try:
            membership = request.user.memberships.select_related("site").first()
        except Exception:
            membership = None
        if membership:
            site_id = membership.site_id
            request.session[SITE_SESSION_KEY] = site_id

    if not site_id:
        return None

    from apps.sites_mgmt.models import Site

    return Site.objects.filter(pk=site_id).first()


def set_active_site(request, site_id: int) -> None:
    request.session[SITE_SESSION_KEY] = int(site_id)


def get_user_sites(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return []
    from apps.sites_mgmt.models import Site

    return Site.objects.filter(memberships__user=user).distinct()


class ActiveSiteMiddleware:
    """Attach ``request.active_site`` on every request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_site = get_active_site(request)
        return self.get_response(request)
