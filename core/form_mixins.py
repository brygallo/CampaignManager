"""Form-view mixins shared across the project.

Plug into superadmin's ``ModelSite`` via the ``form_mixins`` attribute
(or ``create_mixins`` / ``update_mixins`` for asymmetric behavior).
"""
from superadmin.shortcuts import get_urls_of_site


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
