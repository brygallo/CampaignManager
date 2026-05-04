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
        ("anulad",   "cross-circle", "danger"),
        ("cancel",   "cross-circle", "danger"),
        ("rechaz",   "cross-square", "danger"),
        ("finaliz",  "check-circle", "success"),
        ("terminad", "check-circle", "success"),
        ("cerrad",   "lock-2",       "success"),
        ("closed",   "lock-2",       "success"),
        ("aprobad",  "verify",       "success"),
        ("ejecu",    "rocket",       "primary"),
        ("activ",    "rocket",       "primary"),
        ("active",   "rocket",       "primary"),
        ("publicad", "global",       "primary"),
        ("pendient", "time",         "warning"),
        ("pres",     "time",         "warning"),
        ("revisi",   "magnifier",    "info"),
        ("borrador", "document",     "warning"),
        ("draft",    "document",     "warning"),
    )

    # ----- helpers -----

    def _request_params_without_state(self):
        params = self.request.GET.copy()
        params.pop(self.state_filter_param, None)
        params.pop("page", None)
        return params

    def get_state_filter_value(self):
        return self.request.GET.get(self.state_filter_param) or ""

    def get_workflow_choices(self):
        model = self.model
        workflow = getattr(model, "workflow", None)
        if not workflow:
            return ()
        return tuple(
            (str(value), str(label)) for value, label in workflow.choices
        )

    def get_state_filter_item_meta(self, label):
        ll = (label or "").lower()
        for needle, icon, css in self.STATE_META_RULES:
            if needle in ll:
                return icon, css
        return "abstract-26", "info"

    def _base_queryset_for_counts(self):
        """Re-run parent ``get_queryset`` ignoring the state filter param."""
        original = self.request.GET
        self.request.GET = self._request_params_without_state()
        try:
            return super().get_queryset()
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
        counts = dict(
            base_qs.values("state").annotate(c=Count("state")).values_list("state", "c")
        )

        current = self.get_state_filter_value()
        base_params = self._request_params_without_state()
        base_qs_string = base_params.urlencode()
        path = self.request.path

        def make_url(extra=None):
            params = base_params.copy()
            if extra:
                params[self.state_filter_param] = extra
            qs = params.urlencode()
            return f"{path}?{qs}" if qs else path

        items = [{
            "value": "",
            "label": "Todos",
            "count": base_qs.count(),
            "css": "primary",
            "icon": "row-horizontal",
            "url": make_url(),
            "active": not current,
        }]

        for value, label in choices:
            icon, css = self.get_state_filter_item_meta(label)
            items.append({
                "value": value,
                "label": label,
                "count": counts.get(int(value), 0),
                "css": css,
                "icon": icon,
                "url": make_url(value),
                "active": current == value,
            })

        context["state_filter_items"] = items
        context["state_filter_total"] = base_qs.count()
        context["current_state_filter"] = current
        return context
