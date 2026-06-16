"""Pure / small reusable helpers for the authentication app.

Mirrors sim's ``utils.py`` convention — small, reusable, side-effect-free
helpers: safe-redirect validation and superadmin URL resolution. They are
kept here so the views stay thin.
"""
from django.utils.http import url_has_allowed_host_and_scheme


def safe_redirect_target(request, candidate):
    """Return ``candidate`` only if it is an internal URL; otherwise ``"/"``."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return "/"


def site_urls_for(model, instance, user=None):
    """Resolve list/detail/update/delete URLs of a model registered in superadmin."""
    try:
        from superadmin import site as superadmin_site
        from superadmin.shortcuts import get_urls_of_site
    except ImportError:
        return {}
    if not superadmin_site.is_registered(model):
        return {}
    model_site = superadmin_site.get_modelsite(model)
    return get_urls_of_site(model_site, object=instance, user=user)
