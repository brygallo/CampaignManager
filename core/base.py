"""Base classes used to register models in superadmin."""
from superadmin.options import ModelSite

from core.form_mixins import SaveOptionsMixin


class BaseSite(ModelSite):
    """Project-wide default ModelSite.

    Templates point to ``templates/base/*`` (Maxton vertical-menu light theme).
    URL suffixes are translated to Spanish so end users see ``/listar/``,
    ``/crear/``, ``/editar/``, ``/eliminar/`` instead of the English defaults.

    ``SaveOptionsMixin`` is wired into all create / update views so the
    Django-admin-style ``_continue`` / ``_addanother`` / ``_save`` submit
    buttons in ``base_form.html`` redirect to the right URL.
    """

    list_template_name = "base/base_list.html"
    form_template_name = "base/base_form.html"
    detail_template_name = "base/base_detail.html"
    delete_template_name = "base/base_confirm_delete.html"

    url_list_suffix = "listar"
    url_create_suffix = "crear"
    url_update_suffix = "editar"
    url_detail_suffix = ""
    url_delete_suffix = "eliminar"

    paginate_by = 25
    form_mixins = (SaveOptionsMixin,)
