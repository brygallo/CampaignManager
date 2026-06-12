from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse

from core.context_processors import tenant_features


class MapInitialLocationMixin:
    """Prefill coordinate fields and map widget state.

    Server-side defaults come from the active tenant's ``TenantSettings``
    (``map_center_*`` and ``map_default_zoom``). Map-click query params
    (``?lat=…&lng=…&map_zoom=…&map_layer=…``) take precedence so deep links
    keep working.
    """

    coordinate_initial_fields = ()
    map_location_field = "location"
    allowed_map_layers = {"carto", "osm", "satellite"}

    def get_initial(self):
        initial = super().get_initial()
        for field in self.coordinate_initial_fields:
            value = self.request.GET.get(field)
            if value:
                initial[field] = value
        return initial

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        field = form.fields.get(self.map_location_field)
        if not field:
            return form

        tenant_center = tenant_features(self.request).get("tenant_map_center") or {}
        if tenant_center.get("lat") is not None:
            field.widget.attrs.setdefault("data-default-lat", tenant_center["lat"])
        if tenant_center.get("lng") is not None:
            field.widget.attrs.setdefault("data-default-lng", tenant_center["lng"])
        if tenant_center.get("zoom") is not None:
            field.widget.attrs.setdefault("data-default-zoom", tenant_center["zoom"])

        zoom = self.request.GET.get("map_zoom")
        if zoom:
            try:
                parsed_zoom = int(float(zoom))
            except (TypeError, ValueError):
                parsed_zoom = None
            if parsed_zoom is not None:
                field.widget.attrs["data-default-zoom"] = max(1, min(parsed_zoom, 20))

        layer = self.request.GET.get("map_layer")
        if layer in self.allowed_map_layers:
            field.widget.attrs["data-default-basemap"] = layer

        return form


class MapAjaxCreateMixin:
    """Render and submit create forms inside map modals."""

    map_form_template_name = None
    map_detail_url_name = None

    def _is_map_ajax(self):
        return self.request.headers.get("X-Map-Create") == "1"

    def get_map_form_template_name(self):
        if not self.map_form_template_name:
            raise ImproperlyConfigured("map_form_template_name is required.")
        return self.map_form_template_name

    def get_map_detail_url_name(self):
        if not self.map_detail_url_name:
            raise ImproperlyConfigured("map_detail_url_name is required.")
        return self.map_detail_url_name

    def get_map_object_label(self):
        return getattr(self.object, "code", None) or str(self.object)

    def _map_form_inlines(self, form):
        """Superadmin inline formsets, when the site declares them."""
        inlines = getattr(form, "inlines", None)
        if inlines is None and hasattr(self, "get_inlines"):
            inlines = self.get_inlines()
        return inlines

    def _render_map_form(self, form):
        return render_to_string(
            self.get_map_form_template_name(),
            {
                "form": form,
                "action_url": self.request.get_full_path(),
                "inlines": self._map_form_inlines(form),
            },
            request=self.request,
        )

    def get(self, request, *args, **kwargs):
        if self._is_map_ajax():
            form = self.get_form()
            return JsonResponse({"html": self._render_map_form(form)})
        return super().get(request, *args, **kwargs)

    def form_invalid(self, form):
        if self._is_map_ajax():
            return JsonResponse(
                {"ok": False, "html": self._render_map_form(form)},
                status=400,
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self._is_map_ajax():
            return JsonResponse(
                {
                    "ok": True,
                    "id": self.object.pk,
                    "label": self.get_map_object_label(),
                    "url": reverse(
                        self.get_map_detail_url_name(),
                        kwargs={"pk": self.object.pk},
                    ),
                }
            )
        return response


class MapAjaxUpdateMixin:
    """Render and submit update forms inside map modals.

    Mirrors ``MapAjaxCreateMixin`` for the update flow. Triggered by the
    ``X-Map-Update: 1`` request header sent from the map JS.
    """

    map_form_template_name = None

    def _is_map_ajax(self):
        return self.request.headers.get("X-Map-Update") == "1"

    def get_map_form_template_name(self):
        if not self.map_form_template_name:
            raise ImproperlyConfigured("map_form_template_name is required.")
        return self.map_form_template_name

    def get_map_object_label(self):
        return getattr(self.object, "code", None) or str(self.object)

    def _map_form_inlines(self, form):
        """Superadmin inline formsets, when the site declares them."""
        inlines = getattr(form, "inlines", None)
        if inlines is None and hasattr(self, "get_inlines"):
            inlines = self.get_inlines()
        return inlines

    def _render_map_form(self, form):
        return render_to_string(
            self.get_map_form_template_name(),
            {
                "form": form,
                "action_url": self.request.get_full_path(),
                "is_update": True,
                "inlines": self._map_form_inlines(form),
            },
            request=self.request,
        )

    def get(self, request, *args, **kwargs):
        if self._is_map_ajax():
            self.object = self.get_object()
            form = self.get_form()
            return JsonResponse(
                {
                    "html": self._render_map_form(form),
                    "label": self.get_map_object_label(),
                }
            )
        return super().get(request, *args, **kwargs)

    def form_invalid(self, form):
        if self._is_map_ajax():
            return JsonResponse(
                {"ok": False, "html": self._render_map_form(form)},
                status=400,
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self._is_map_ajax():
            return JsonResponse(
                {
                    "ok": True,
                    "id": self.object.pk,
                    "label": self.get_map_object_label(),
                }
            )
        return response


class MapAjaxDeleteMixin:
    """Accept AJAX deletes from the map modal.

    Triggered by the ``X-Map-Delete: 1`` request header. Returns JSON instead
    of redirecting so the map JS can refresh the markers in place.
    """

    def _is_map_ajax(self):
        return self.request.headers.get("X-Map-Delete") == "1"

    def post(self, request, *args, **kwargs):
        if self._is_map_ajax():
            self.object = self.get_object()
            pk = self.object.pk
            self.object.delete()
            return JsonResponse({"ok": True, "id": pk})
        return super().post(request, *args, **kwargs)

    # Some clients send DELETE via POST emulation; both land in post().
    delete = post
