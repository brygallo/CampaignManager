"""Active-campaign session helpers and middleware.

Most tenants run a single campaign at a time, but the UI must keep working
when there is more than one. The "active campaign" is stored in the session
(``session["active_campaign_id"]``) and resolved once per request by
``ActiveCampaignMiddleware`` into ``request.active_campaign``. All other
plumbing (form mixin, queryset scope, navbar selector) consumes that
attribute and never touches the session directly.

Scope is tenant-safe by construction: sessions already live inside the
tenant schema thanks to ``core.middleware.TenantAwareSessionMiddleware``,
and the middleware always queries ``Campaign.objects`` from the active
schema before trusting the id.
"""
from __future__ import annotations

from django.db import DatabaseError
from django_tenants.utils import get_public_schema_name

SESSION_KEY = "active_campaign_id"
SESSION_ALL_KEY = "active_campaign_all"
VIEW_HISTORICAL_CAMPAIGNS_PERM = "campaigns.view_historical_campaigns"


def _campaign_model():
    """Lazy import so middleware import order stays decoupled from app loading."""
    from apps.campaigns.models import Campaign

    return Campaign


def _is_tenant_request(request) -> bool:
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return False
    return getattr(tenant, "schema_name", None) != get_public_schema_name()


def can_view_historical_campaigns(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser or user.has_perm(VIEW_HISTORICAL_CAMPAIGNS_PERM))


def visible_campaigns_queryset(queryset, user):
    if can_view_historical_campaigns(user):
        return queryset
    return queryset.filter(is_active=True)


def is_campaign_read_only(campaign) -> bool:
    """True when records must not be created/edited under ``campaign``.

    Archived campaigns (``is_active=False``) and campaigns in a terminal
    workflow state (CLOSED / CANCELED) are browsing-only scopes: lists may
    still be filtered by them, but forms must ask for an operational
    campaign explicitly.
    """
    if campaign is None:
        return False
    if not getattr(campaign, "is_active", True):
        return True
    workflow = getattr(type(campaign), "workflow", None)
    if workflow is None:
        return False
    return campaign.state in {workflow.CLOSED, workflow.CANCELED}


def get_session_campaign_id(request) -> int | None:
    """Return the campaign id stored in the session, or ``None``."""
    session = getattr(request, "session", None)
    if session is None:
        return None
    raw = session.get(SESSION_KEY)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def set_active_campaign(request, campaign) -> None:
    """Persist the campaign id in the session and refresh ``request.active_campaign``."""
    request.session[SESSION_KEY] = int(campaign.pk)
    request.session.pop(SESSION_ALL_KEY, None)
    request.active_campaign = campaign


def clear_active_campaign(request) -> None:
    request.session.pop(SESSION_KEY, None)
    request.session[SESSION_ALL_KEY] = True
    request.active_campaign = None


def resolve_active_campaign(request):
    """Return the active campaign for this request.

    Resolution order:
      1. The id stored in ``session["active_campaign_id"]`` if it still
         resolves to a real campaign in the tenant.
      2. The campaign explicitly flagged ``is_default=True`` in the tenant.
      3. The only campaign in the tenant when exactly one exists.
      4. ``None`` otherwise (user must pick from the "Todas" navbar dropdown).

    Steps 2 and 3 also persist the resolved id back into the session so
    subsequent requests skip the lookup.
    """
    if not _is_tenant_request(request):
        return None

    Campaign = _campaign_model()
    stored_id = get_session_campaign_id(request)

    try:
        if stored_id is not None:
            stored_qs = Campaign.objects.filter(pk=stored_id)
            # Users with the historical-campaigns permission may keep an
            # archived campaign selected (read-only browsing scope).
            if not can_view_historical_campaigns(getattr(request, "user", None)):
                stored_qs = stored_qs.filter(is_active=True)
            campaign = stored_qs.first()
            if campaign is not None:
                return campaign
            # Stored id no longer points anywhere — drop it before falling back.
            request.session.pop(SESSION_KEY, None)

        if request.session.get(SESSION_ALL_KEY):
            return None

        # 2) Prefer the campaign explicitly marked as default.
        default = Campaign.objects.filter(is_default=True, is_active=True).first()
        if default is not None:
            request.session[SESSION_KEY] = int(default.pk)
            request.session.pop(SESSION_ALL_KEY, None)
            return default

        # 3) Auto-select when there is exactly one campaign in the tenant.
        candidates = list(Campaign.objects.filter(is_active=True)[:2])
        if len(candidates) == 1:
            request.session[SESSION_KEY] = int(candidates[0].pk)
            request.session.pop(SESSION_ALL_KEY, None)
            return candidates[0]
    except DatabaseError:
        return None

    return None


def scope_queryset_to_active_campaign(queryset, request, field: str = "campaign"):
    """Apply ``filter(<field>=active_campaign)`` when one is set.

    Helper for views and ad-hoc dashboards that don't go through superadmin /
    ``BaseSite`` (and therefore miss the ``ActiveCampaignScopeMixin``). Always
    returns a queryset of the same type; no-op when:

      - ``request.active_campaign`` is ``None`` (user is in "Todas" mode),
      - the model doesn't expose the named field.

    Use ``field="campaign_id"`` (or similar) for relations named differently.
    """
    active = getattr(request, "active_campaign", None)
    model = queryset.model
    base_field = field.split("__", 1)[0].rstrip("_id")
    try:
        scoped_field = model._meta.get_field(base_field)
    except Exception:
        return queryset
    if active is not None:
        return queryset.filter(**{field: active.pk})
    if can_view_historical_campaigns(getattr(request, "user", None)):
        return queryset
    related_model = getattr(getattr(scoped_field, "remote_field", None), "model", None)
    if related_model is _campaign_model():
        return queryset.filter(**{f"{base_field}__is_active": True})
    return queryset


def list_available_campaigns(request_or_user=None, limit: int = 50):
    """Return a small, ordered queryset for the navbar selector.

    Default campaign first, then ACTIVE state (workflow value 1), then
    newest by ``start_date``. Archived campaigns sink to the bottom and
    only appear for users with the historical-campaigns permission
    (``visible_campaigns_queryset`` hides them otherwise). Empty queryset
    is fine — callers handle the "no campaigns yet" case.
    """
    Campaign = _campaign_model()
    workflow = Campaign.workflow
    user = getattr(request_or_user, "user", request_or_user)
    return (
        visible_campaigns_queryset(Campaign.objects.all(), user)
        .select_related("candidate", "movement")
        .order_by(
            "-is_default",
            "-is_active",
            # ACTIVE first, everything else after.
            models_case_active(workflow.ACTIVE),
            "-start_date",
            "name",
        )[:limit]
    )


def models_case_active(active_value):
    """``Case(When(state=ACTIVE, then=0), default=1)`` as an ordering expr."""
    from django.db.models import Case, IntegerField, Value, When

    return Case(
        When(state=active_value, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    ).asc()


class ActiveCampaignMiddleware:
    """Populate ``request.active_campaign`` once per request.

    Runs after ``TenantPathRoutingMiddleware`` and the session middleware so
    both ``request.tenant`` and ``request.session`` are available. No-op on
    the public schema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_campaign = resolve_active_campaign(request)
        return self.get_response(request)
