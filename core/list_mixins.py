"""List-view mixins (port of ``WorkflowStateFilterMixin`` from sim).

Renders state-filter cards on top of a list view for models that have a
``workflow`` attribute (see ``apps/workflows``) and a ``state`` field with
choices. Designed to plug into superadmin's ``ModelSite`` via the
``list_mixins`` attribute on a ``@register``-ed site class.

The cards consume Metronic v10 ``ki-outline`` icon names (no Font Awesome
or Material Icons) and Bootstrap color names — see ``base_list.html``
for the exact rendering contract.
"""

from django.db.models import Count
from django.urls import reverse

from superadmin.services import FieldService, FilterService


DEFAULT_LOOKUP_BY_TYPE = {
    "ForeignKey": "exact",
    "OneToOneField": "exact",
    "ManyToManyField": "exact",
    "BooleanField": "exact",
    "CharField": "icontains",
    "TextField": "icontains",
    "SlugField": "icontains",
    "EmailField": "icontains",
    "IntegerField": "exact",
    "PositiveIntegerField": "exact",
    "BigIntegerField": "exact",
    "DecimalField": "exact",
    "FloatField": "exact",
    "DateField": "gte",
    "DateTimeField": "gte",
}


def default_lookup_for_type(field_type):
    """Return the default lookup to use for a Django field type.

    Why: in the demo55 dropdown the user picks a value, not a lookup —
    so we infer a sensible default per type (FK/choices → exact, CharField →
    icontains, dates → gte for the lower-bound input of a range).
    """
    return DEFAULT_LOOKUP_BY_TYPE.get(field_type, "exact")


class ActiveCampaignScopeMixin:
    """Restrict list/detail querysets to the active campaign.

    Opt-out per site with ``respect_active_campaign = False`` (default is
    ``True``). The mixin auto-detects whether the bound model exposes the
    expected FK and is a no-op for models without it (e.g. ``Election``,
    ``PoliticalMovement``) or when no active campaign is set.

    Plug into ``BaseSite.list_mixins`` and ``BaseSite.detail_mixins`` so
    every CRUD view inherits the scope without per-site wiring.

    NOT an authorization control.
        The active campaign is a per-session UX preference the user picks
        from the navbar. Any logged-in user in the tenant can switch it to
        any campaign at will, so this filter must not be the only thing
        keeping a user away from records they shouldn't see. Per-user /
        per-role authorization belongs in a separate mixin (cf.
        ``FieldSurveyOwnershipMixin``).
    """

    active_campaign_field = "campaign"

    def _scope_field_name(self):
        return getattr(self.site, "active_campaign_field", self.active_campaign_field)

    def _scope_enabled(self) -> bool:
        if not getattr(self.site, "respect_active_campaign", True):
            return False
        field_name = self._scope_field_name()
        model = getattr(self.site, "model", None) or getattr(self, "model", None)
        if model is None:
            return False
        try:
            model._meta.get_field(field_name)
        except Exception:
            return False
        return True

    def get_queryset(self):
        qs = super().get_queryset()
        if not self._scope_enabled():
            return qs
        active = getattr(self.request, "active_campaign", None)
        if active is None:
            # "Todas" mode mixes records from several campaigns, and
            # ``get_context_data`` labels each row with its campaign —
            # prefetch the FK so that doesn't become an N+1.
            return qs.select_related(self._scope_field_name())
        return qs.filter(**{self._scope_field_name(): active.pk})

    def get_context_data(self, **kwargs):
        """Label rows with their campaign while browsing in "Todas" mode.

        Records from several campaigns are mixed in the same table, so each
        row needs to say which campaign it belongs to (rendered by
        ``base_list.html`` next to the first column).
        """
        context = super().get_context_data(**kwargs)
        if not self._scope_enabled():
            return context
        if getattr(self.request, "active_campaign", None) is not None:
            return context
        context["campaign_scope_all_mode"] = True
        site_ctx = context.get("site")
        rows = site_ctx.get("rows") if isinstance(site_ctx, dict) else None
        if not rows:
            return context
        field_name = self._scope_field_name()
        for row in rows:
            campaign = getattr(row.get("instance"), field_name, None)
            row["campaign_label"] = str(campaign) if campaign else ""
        return context


class OrderingMixin:
    """Honor ``?ordering=<field>`` in the URL so list sort is shareable.

    Click on a column header sends the user to ``?ordering=<field>``; a second
    click flips to ``?ordering=-<field>``. The queryset is reordered server
    side, which means the order is the same regardless of pagination and the
    URL can be bookmarked or shared.

    To avoid leaking model internals via crafted URLs, the field name must
    appear in either ``site.orderable_fields`` (explicit allowlist) or, by
    default, in ``site.list_fields`` — the same columns the user sees. The
    ``field:Label`` shorthand is supported: only the part before the colon
    is matched against the request.
    """

    @staticmethod
    def _strip_display_method(name):
        """``get_<field>_display`` → ``<field>`` so state columns sort cleanly.

        ``get_state_display`` etc. is the Django convention for rendering a
        choices field's label. The user clicks the column to sort by the
        underlying enum, so we translate before consulting the model.
        """
        if name.startswith("get_") and name.endswith("_display"):
            return name[len("get_"):-len("_display")]
        return name

    def _orderable_fields(self):
        site_obj = getattr(self, "site", None)
        explicit = getattr(site_obj, "orderable_fields", None)
        if explicit:
            return {str(name) for name in explicit}
        list_fields = getattr(site_obj, "list_fields", ()) or ()
        return {self._strip_display_method(str(name).split(":", 1)[0]) for name in list_fields}

    def get_queryset(self):
        qs = super().get_queryset()
        ordering = (self.request.GET.get("ordering") or "").strip()
        if not ordering:
            return qs
        field = ordering.lstrip("-")
        if field not in self._orderable_fields():
            return qs
        return qs.order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ordering = (self.request.GET.get("ordering") or "").strip()
        descending = ordering.startswith("-")
        ordering_info = {
            "current": ordering,
            "field": ordering.lstrip("-"),
            "direction": "desc" if descending else ("asc" if ordering else ""),
            "orderable_fields": list(self._orderable_fields()),
        }
        site_ctx = context.get("site")
        if isinstance(site_ctx, dict):
            site_ctx["ordering"] = ordering_info
        else:
            context["site"] = {"ordering": ordering_info}
        return context


class DropdownFilterMixin:
    """Enrich ``site.filter_fields`` with rendering-ready options.

    The Metronic demo55 filter dropdown renders all filters at once with
    pre-loaded choices (no AJAX). This mixin exposes
    ``site.filter_options`` and ``site.filter_session_url`` so
    ``base_list.html`` can render a static dropdown.

    Usage in an app's ``sites.py``::

        @register(MyModel)
        class MySite(ModelSite):
            filter_fields = ("estado:Estado", "candidato")
            list_mixins = (DropdownFilterMixin, ...)
    """

    def _get_session_params(self):
        return FilterService.get_params(self.site.model, self.request.session)

    def _build_filter_option(self, field_def, params):
        model = self.site.model
        name = field_def.split(":")[0]
        try:
            field_type = FieldService.get_field_type(model, name)
        except Exception:
            field_type = "CharField"

        default_lookup = default_lookup_for_type(field_type)

        try:
            raw_choices = FilterService.get_choices(model, name)
        except Exception:
            raw_choices = []

        if hasattr(raw_choices, "model"):
            choices_list = [(obj.pk, str(obj)) for obj in raw_choices]
        else:
            choices_list = list(raw_choices) if raw_choices else []

        is_date = field_type in ("DateField", "DateTimeField")
        is_select = bool(choices_list) or field_type == "BooleanField"

        option = {
            "name": name,
            "label": FieldService.get_field_label(model, field_def),
            "field_type": field_type,
            "default_lookup": default_lookup,
            "choices": choices_list,
            "is_select": is_select,
            "is_date": is_date,
            "is_text": not is_select and not is_date,
            "current_value": params.get(f"{name}__{default_lookup}", ""),
        }

        if is_date:
            option["current_value_gte"] = params.get(f"{name}__gte", "")
            option["current_value_lte"] = params.get(f"{name}__lte", "")

        return option

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_obj = getattr(self, "site", None)
        if not site_obj or not getattr(site_obj, "filter_fields", None):
            return context

        params = self._get_session_params()
        options = [
            self._build_filter_option(field_def, params) for field_def in site_obj.filter_fields
        ]

        session_url = reverse(
            "site:session",
            args=[
                site_obj.model._meta.app_label,
                site_obj.model._meta.model_name,
            ],
        )

        site_ctx = context.get("site")
        if isinstance(site_ctx, dict):
            site_ctx["filter_options"] = options
            site_ctx["filter_session_url"] = session_url
        else:
            context["site"] = {
                "filter_options": options,
                "filter_session_url": session_url,
            }
        return context


class WorkflowStateFilterMixin:
    """Render state-filter cards and apply the filter to the queryset.

    Context added:

    - ``state_filter_items`` — list of dicts (``url``, ``label``, ``count``,
      ``active``, ``icon``, ``css``, ``value``).
    - ``state_filter_total`` — count when no state filter is applied.
    - ``current_state_filter`` — current filter value, if any.
    """

    state_filter_param = "state"

    # (lowercased substring of the label, ki-* icon name, Bootstrap color).
    # First match wins; fall back is ``("abstract-26", "info")``.
    STATE_META_RULES = (
        ("anulad", "cross-circle", "danger"),
        ("cancel", "cross-circle", "danger"),
        ("rechaz", "cross-square", "danger"),
        ("finaliz", "check-circle", "success"),
        ("terminad", "check-circle", "success"),
        ("cerrad", "lock-2", "success"),
        ("closed", "lock-2", "success"),
        ("aprobad", "verify", "success"),
        ("ejecu", "rocket", "primary"),
        ("activ", "rocket", "primary"),
        ("active", "rocket", "primary"),
        ("publicad", "global", "primary"),
        ("pendient", "time", "warning"),
        ("pres", "time", "warning"),
        ("revisi", "magnifier", "info"),
        ("borrador", "document", "warning"),
        ("draft", "document", "warning"),
    )

    # ----- helpers -----

    def _request_params_without_state(self):
        params = self.request.GET.copy()
        params.pop(self.state_filter_param, None)
        params.pop("page", None)
        return params

    def _request_visible_path(self):
        path = self.request.path
        prefix = getattr(self.request, "tenant_path_prefix", "")
        if prefix and not path.startswith(f"{prefix}/"):
            return f"{prefix}{path}"
        return path

    def get_state_filter_value(self):
        return self.request.GET.get(self.state_filter_param) or ""

    def get_workflow_choices(self):
        model = self.model
        workflow = getattr(model, "workflow", None)
        if not workflow:
            return ()
        return tuple((str(value), str(label)) for value, label in workflow.choices)

    def get_state_filter_item_meta(self, label):
        ll = (label or "").lower()
        for needle, icon, css in self.STATE_META_RULES:
            if needle in ll:
                return icon, css
        return "abstract-26", "info"

    def _base_queryset_for_counts(self):
        """Re-run ``self.get_queryset`` ignoring the state filter param.

        Uses ``self.get_queryset()`` (not ``super().get_queryset()``) so the
        full MRO chain runs — most importantly ``ActiveCampaignScopeMixin``,
        which sits above this mixin in the bases tuple (it is prepended by
        ``BaseSite``). Calling ``super()`` here would skip that scope and
        produce tab counts that don't match the table below them.
        """
        original = self.request.GET
        self.request.GET = self._request_params_without_state()
        try:
            return self.get_queryset()
        finally:
            self.request.GET = original

    # ----- ListView hooks -----

    def get_queryset(self):
        qs = super().get_queryset()
        value = self.get_state_filter_value()
        if value and value.lstrip("-").isdigit():
            qs = qs.filter(state=int(value))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        choices = self.get_workflow_choices()
        if not choices:
            return context

        base_qs = self._base_queryset_for_counts()
        counts = dict(base_qs.values("state").annotate(c=Count("state")).values_list("state", "c"))
        total_count = base_qs.count()

        current = self.get_state_filter_value()
        base_params = self._request_params_without_state()
        path = self._request_visible_path()

        def make_url(extra=None):
            params = base_params.copy()
            if extra:
                params[self.state_filter_param] = extra
            qs = params.urlencode()
            return f"{path}?{qs}" if qs else path

        items = [
            {
                "value": "",
                "label": "Todos",
                "count": total_count,
                "css": "primary",
                "icon": "row-horizontal",
                "url": make_url(),
                "active": not current,
            }
        ]

        for value, label in choices:
            icon, css = self.get_state_filter_item_meta(label)
            items.append(
                {
                    "value": value,
                    "label": label,
                    "count": counts.get(int(value), 0),
                    "css": css,
                    "icon": icon,
                    "url": make_url(value),
                    "active": current == value,
                }
            )

        context["state_filter_items"] = items
        context["state_filter_total"] = total_count
        context["current_state_filter"] = current
        return context
