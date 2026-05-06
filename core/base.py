"""Base classes used to register models in superadmin."""
import json

from superadmin.options import ModelSite

from core.form_mixins import SaveOptionsMixin


class DetailMapsMixin:
    """Add read-only map definitions to detail pages."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        detail_maps = self.site.get_detail_maps(self.object)
        if "site" in context:
            context["site"]["detail_maps"] = detail_maps
        else:
            context["site"] = {"detail_maps": detail_maps}
        return context


class HideEmptyFieldsetsMixin:
    """Hide detail fieldsets when every field in them is empty.

    Useful for workflow-driven detail pages: downstream sections (approval,
    installation, damage, retirement, ...) only appear after the matching
    transition has captured data. Sections listed in ``always_visible_fieldsets``
    on the site are kept regardless.
    """

    def get_results(self):
        flatten_results, fieldsets = super().get_results()
        always = set(getattr(self.site, "always_visible_fieldsets", ()))
        kept = [
            fs for fs in fieldsets
            if fs.get("title", "") in always or self._fieldset_has_value(fs)
        ]
        return flatten_results, kept

    @staticmethod
    def _fieldset_has_value(fieldset_block):
        for row in fieldset_block.get("fieldset", []):
            for field_tuple in row.get("fields", ()):  # (label, value, type, field)
                if len(field_tuple) < 2:
                    continue
                value = field_tuple[1]
                if value is None:
                    continue
                if hasattr(value, "name") and not getattr(value, "name", ""):
                    continue  # empty FileField/ImageField
                if isinstance(value, str) and not value.strip():
                    continue
                return True
        return False


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
    detail_mixins = (DetailMapsMixin,)
    detail_maps = ()

    create_success_url = "detail"
    update_success_url = "detail"

    url_list_suffix = "listar"
    url_create_suffix = "crear"
    url_update_suffix = "editar"
    url_detail_suffix = ""
    url_delete_suffix = "eliminar"

    paginate_by = 25
    form_mixins = (SaveOptionsMixin,)

    def get_detail_maps(self, obj):
        """Resolve declarative ``detail_maps`` against ``obj``.

        Supports three shapes per entry:
          - tuple ``("Title", "lat_field", "lng_field"[, zoom])`` — one marker.
          - dict ``{"title": ..., "lat": ..., "lng": ..., "zoom": ...}`` — one marker.
          - dict with ``"points": [{"label", "lat", "lng", "color"}, ...]`` —
            several markers on the same canvas, distinguished by label/color.
        Entries (or individual points) without resolved coordinates are dropped.
        """
        maps = []
        for config in self.detail_maps:
            if isinstance(config, dict) and "points" in config:
                title = config.get("title", "Ubicaciones")
                zoom = config.get("zoom", 16)
                resolved_points = []
                for point in config["points"]:
                    lat_field = point.get("lat") or point.get("latitude")
                    lng_field = point.get("lng") or point.get("longitude")
                    latitude = getattr(obj, lat_field, None) if lat_field else None
                    longitude = getattr(obj, lng_field, None) if lng_field else None
                    if latitude in (None, "") or longitude in (None, ""):
                        continue
                    resolved_points.append(
                        {
                            "label": point.get("label", "Ubicación"),
                            "color": point.get("color"),
                            "latitude": float(latitude),
                            "longitude": float(longitude),
                        }
                    )
                if not resolved_points:
                    continue
                maps.append(
                    {
                        "title": title,
                        "zoom": zoom,
                        "points": resolved_points,
                        "points_json": json.dumps(resolved_points),
                    }
                )
                continue

            if isinstance(config, dict):
                title = config.get("title", "Ubicación")
                lat_field = config.get("lat") or config.get("latitude")
                lng_field = config.get("lng") or config.get("longitude")
                zoom = config.get("zoom", 16)
            else:
                title, lat_field, lng_field, *rest = config
                zoom = rest[0] if rest else 16

            latitude = getattr(obj, lat_field, None) if lat_field else None
            longitude = getattr(obj, lng_field, None) if lng_field else None
            if latitude in (None, "") or longitude in (None, ""):
                continue

            maps.append(
                {
                    "title": title,
                    "latitude": latitude,
                    "longitude": longitude,
                    "zoom": zoom,
                    "lat_field": lat_field,
                    "lng_field": lng_field,
                }
            )
        return maps
