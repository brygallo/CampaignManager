"""Form-view mixins shared across the project.

Plug into superadmin's ``ModelSite`` via the ``form_mixins`` attribute
(or ``create_mixins`` / ``update_mixins`` for asymmetric behavior).
"""
from django import forms

from superadmin.shortcuts import get_urls_of_site


class ActiveCampaignFormMixin:
    """Auto-fill and lock the ``campaign`` field from the active campaign.

    The mixin is intentionally view-level (not form-level) so individual
    ``ModelForm`` subclasses don't need to learn about the request. When
    the bound model exposes a ``campaign`` FK and the request has an
    ``active_campaign``, the mixin:

      - pre-selects the campaign as initial (Create) or instance fk (Update),
      - restricts the queryset to that single campaign so no other choice
        can be POSTed back,
      - swaps the widget for a ``HiddenInput`` so the form keeps validating
        the field without showing it.

    Sites opt out by setting ``respect_active_campaign = False`` on the
    ``ModelSite``. The mixin is a no-op when no active campaign is set
    (auto-select handles the single-campaign case in the middleware).
    """

    active_campaign_field = "campaign"

    def _campaign_field_name(self):
        return getattr(self.site, "active_campaign_field", self.active_campaign_field)

    def _site_respects_active_campaign(self) -> bool:
        return getattr(self.site, "respect_active_campaign", True)

    def _model_has_campaign_field(self) -> bool:
        field_name = self._campaign_field_name()
        try:
            self.site.model._meta.get_field(field_name)
        except Exception:
            return False
        return True

    def _active_campaign_is_editable(self, active) -> bool:
        """Return True when records can be created/edited under ``active``.

        CLOSED and CANCELED campaigns are terminal states (`read_only=True`
        in ``CampaignWorkflow``). The session-level "active campaign" is
        still useful for browsing scope on those, but the create/update
        forms must not silently associate new records with them.
        """
        if active is None:
            return False
        workflow = getattr(type(active), "workflow", None)
        if workflow is None:
            return True
        terminal = {workflow.CLOSED, workflow.CANCELED}
        return active.state not in terminal

    def get_initial(self):
        initial = super().get_initial()
        active = getattr(self.request, "active_campaign", None)
        if (
            active is not None
            and self._active_campaign_is_editable(active)
            and self._site_respects_active_campaign()
            and self._model_has_campaign_field()
        ):
            initial.setdefault(self._campaign_field_name(), active.pk)
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        active = getattr(self.request, "active_campaign", None)
        if (
            active is None
            or not self._active_campaign_is_editable(active)
            or not self._site_respects_active_campaign()
            or not self._model_has_campaign_field()
        ):
            # Terminal-state campaigns are not auto-filled: let the user
            # explicitly pick a still-operational campaign instead of
            # silently saving against a closed/canceled one.
            return form

        field_name = self._campaign_field_name()
        field = form.fields.get(field_name)
        if field is None:
            return form

        # Restrict the choices server-side so a forged POST can't break out.
        if hasattr(field, "queryset"):
            field.queryset = field.queryset.filter(pk=active.pk)
            if hasattr(field.widget, "queryset"):
                field.widget.queryset = field.queryset
        field.initial = active.pk
        # Keep validation but hide from the UI — fieldsets keep working
        # because the field still exists on the form.
        field.widget = forms.HiddenInput()
        field.required = True
        return form


class SaveOptionsMixin:
    """Honor Django-admin-style submit buttons in Create / Update views.

    Reads the POST body for the name of the submit button that triggered
    the form and overrides ``get_success_url()`` accordingly:

    - ``_continue`` → keep editing the saved object (URL: ``update``).
    - ``_addanother`` → go to the create page for another object (URL: ``create``).
    - anything else (``_save`` or no name) → fall back to ``site.{create,update}_success_url``.

    Falls through to ``super()`` if the requested URL isn't defined for the
    site (e.g. a read-only model).
    """

    def get_success_url(self):
        post = getattr(self.request, "POST", None) or {}
        urls = get_urls_of_site(self.site, object=self.object)
        if "_continue" in post and urls.get("update"):
            return urls["update"]
        if "_addanother" in post and urls.get("create"):
            return urls["create"]
        return super().get_success_url()
