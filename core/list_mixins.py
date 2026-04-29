"""List-view mixins (port of ``WorkflowStateFilterMixin`` from sim).

Renders state-filter cards on top of a list view for models that have a
``workflow`` attribute (see ``apps/workflows``) and a ``state`` field with
choices.
"""
from django.db.models import Count
from django.urls import reverse


class WorkflowStateFilterMixin:
    """Render state-filter cards and apply the filter to the queryset."""

    state_filter_param = "state"

    # (substring of the lowercased label, css class, material icon)
    STATE_META_RULES = (
        ("anulad",     "danger",  "block"),
        ("cancel",     "danger",  "block"),
        ("rechaz",     "danger",  "highlight_off"),
        ("finaliz",    "success", "done_all"),
        ("terminad",   "success", "done_all"),
        ("aprobad",    "success", "verified"),
        ("ejecu",      "primary", "play_circle"),
        ("publicad",   "primary", "language"),
        ("pres",       "warning", "schedule"),
        ("pendient",   "warning", "schedule"),
        ("revisi",     "info",    "fact_check"),
        ("borrador",   "secondary", "edit"),
        ("draft",      "secondary", "edit"),
    )

    def get_state_filter_value(self):
        return self.request.GET.get(self.state_filter_param)

    def get_workflow_choices(self):
        model = self.site.model
        workflow = getattr(model, "workflow", None)
        if not workflow:
            return ()
        return tuple(
            (str(value), label)
            for value, label in workflow.Choices.choices  # type: ignore[attr-defined]
        )

    def get_state_filter_item_meta(self, label):
        ll = (label or "").lower()
        for needle, css, icon in self.STATE_META_RULES:
            if needle in ll:
                return css, icon
        return "info", "label"

    def get_queryset(self):
        qs = super().get_queryset()
        value = self.get_state_filter_value()
        if value:
            qs = qs.filter(state=value)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        choices = self.get_workflow_choices()
        if not choices:
            return context

        base_qs = super().get_queryset()
        counts = dict(
            base_qs.values("state").annotate(c=Count("state")).values_list("state", "c")
        )

        items = []
        list_url_name = self.site.get_url_name("listar")
        try:
            base_url = reverse(list_url_name)
        except Exception:
            base_url = ""
        for value, label in choices:
            css, icon = self.get_state_filter_item_meta(label)
            items.append({
                "value": value,
                "label": label,
                "count": counts.get(int(value), 0),
                "css": css,
                "icon": icon,
                "url": f"{base_url}?{self.state_filter_param}={value}" if base_url else "#",
                "active": str(self.get_state_filter_value() or "") == str(value),
            })
        context["state_filter_items"] = items
        context["state_filter_total"] = base_qs.count()
        return context
