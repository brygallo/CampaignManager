"""Base classes used to register models in superadmin."""
import json

from django.contrib import messages
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect, JsonResponse

from superadmin.options import ModelSite

from core.audit import AuditContextMixin
from core.form_mixins import ActiveCampaignFormMixin, SaveOptionsMixin
from core.list_mixins import ActiveCampaignScopeMixin, OrderingMixin


class ProtectedDeleteMixin:
    """Render the right flash message for delete views and trap PROTECT errors.

    Two things in one:
    - The base success message inherited from the ``superadmin`` package is
      ``"Se ha guardado correctamente."``, hardcoded for create/update/delete
      alike. For deletes that wording is wrong; we replace it on the queue
      with ``"Se ha eliminado correctamente."``.
    - Django raises ``ProtectedError`` on ``delete()`` when ``on_delete=PROTECT``
      blocks the cascade; without this mixin the exception bubbles up to a
      500 page (under DEBUG=True it leaks a stack trace). We catch it,
      drop the package's misleading "guardado" notice that was queued just
      before the failure, and redirect back with a Spanish error message.

    The ``superadmin`` wrapper class defines ``form_valid`` directly on the
    runtime view, so it wins the MRO over any mixin we prepend; that's why
    we cannot bypass it. We let it run and tweak the messages queue after.
    """

    _SUPERADMIN_SUCCESS_MSG = "Se ha guardado correctamente."

    def _drop_superadmin_success(self):
        """Remove the wrapper's hardcoded success notice from the queue."""
        storage = getattr(self.request, "_messages", None)
        queue = getattr(storage, "_queued_messages", None)
        if queue is None:
            return
        for msg in list(queue):
            if msg.tags == "success" and msg.message == self._SUPERADMIN_SUCCESS_MSG:
                queue.remove(msg)
                break

    def _replace_superadmin_success(self, new_message):
        """Swap the wrapper's hardcoded notice for a delete-specific one."""
        storage = getattr(self.request, "_messages", None)
        queue = getattr(storage, "_queued_messages", None)
        if queue is None:
            messages.success(self.request, new_message)
            return
        for msg in queue:
            if msg.tags == "success" and msg.message == self._SUPERADMIN_SUCCESS_MSG:
                msg.message = new_message
                return
        messages.success(self.request, new_message)

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError as exc:
            self._drop_superadmin_success()
            related_count = len(exc.protected_objects)
            related_label = ""
            if exc.protected_objects:
                first = next(iter(exc.protected_objects))
                related_label = first._meta.verbose_name_plural or first._meta.verbose_name
            detail = f" ({related_count} {related_label})" if related_label else f" ({related_count})"
            messages.error(
                self.request,
                "No se puede eliminar este registro porque tiene información "
                f"relacionada que depende de él{detail}.",
            )
            target = (
                self.object.get_absolute_url()
                if hasattr(self.object, "get_absolute_url")
                else self.request.path
            )
            return HttpResponseRedirect(target)
        self._replace_superadmin_success("Se ha eliminado correctamente.")
        return response


class BlockEditOnReadOnlyStateMixin:
    """Reject ``update_view`` when the workflow state is marked read-only.

    A state opts in via ``dict(read_only=True)`` next to its label in the
    ``WorkflowChoices`` declaration (see ``apps/workflows/__init__.py``).
    Wire this mixin on a ``ModelSite`` via ``update_mixins``; nothing else
    is required because the rule travels with the workflow definition,
    not with the site.
    """

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if hasattr(obj, "is_state_read_only") and obj.is_state_read_only():
            state_label = ""
            current = obj.get_current_state() if hasattr(obj, "get_current_state") else None
            if current is not None:
                state_label = f" ({current.label})"
            error_msg = (
                f"Este registro está en un estado de solo lectura{state_label} "
                "y no puede editarse."
            )
            # Map AJAX requests can't follow a redirect — surface the rejection
            # as JSON so the modal can render a clean error.
            if request.headers.get("X-Map-Update") == "1":
                return JsonResponse({"ok": False, "error": error_msg}, status=409)
            messages.error(request, error_msg)
            target = (
                obj.get_absolute_url()
                if hasattr(obj, "get_absolute_url")
                else request.path.rsplit("/editar/", 1)[0] + "/"
            )
            return HttpResponseRedirect(target)
        return super().dispatch(request, *args, **kwargs)


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

    Templates point to ``templates/base/*`` (Metronic v8 demo55 vertical-menu light theme).
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
    # ``OrderingMixin`` reads ``?ordering=<field>`` from the URL so clicks on
    # column headers reorder the queryset server-side and the URL stays in
    # sync (shareable / bookmarkable). Sites that override ``list_mixins``
    # must re-include it (or any helper they expose, see DropdownFilterMixin).
    # ``ActiveCampaignScopeMixin`` scopes querysets to ``request.active_campaign``
    # for any model that has a ``campaign`` FK (opt out with
    # ``respect_active_campaign = False``).
    list_mixins = (ActiveCampaignScopeMixin, OrderingMixin)
    # ``AuditContextMixin`` populates ``processed_traces`` so the detail
    # template can show the "Auditoría" tab whenever the model has Trace
    # rows. Sites without traces just won't render the tab — the template
    # is already conditional on the context key.
    detail_mixins = (ActiveCampaignScopeMixin, AuditContextMixin, DetailMapsMixin)
    delete_mixins = (ActiveCampaignScopeMixin, ProtectedDeleteMixin)
    detail_maps = ()

    create_success_url = "detail"
    update_success_url = "detail"

    url_list_suffix = "listar"
    url_create_suffix = "crear"
    url_update_suffix = "editar"
    url_detail_suffix = ""
    url_delete_suffix = "eliminar"

    paginate_by = 25
    # ``ActiveCampaignFormMixin`` auto-fills + locks the ``campaign`` FK from
    # ``request.active_campaign`` on create / update forms. Same opt-out flag.
    form_mixins = (ActiveCampaignFormMixin, SaveOptionsMixin)
    # When True (default), CRUD views for models with a ``campaign`` FK are
    # scoped to ``request.active_campaign``. Sites for global catalogs
    # (Election, PoliticalMovement, Position, Candidate, the Campaign list
    # itself) should set this to ``False``.
    respect_active_campaign = True

    # Subclasses commonly redefine ``list_mixins`` / ``detail_mixins`` /
    # ``form_mixins`` / ``create_mixins`` / ``update_mixins`` / ``delete_mixins``
    # to add their own behavior, which would drop our defaults. We re-merge
    # the active-campaign mixins (and ``SaveOptionsMixin``) automatically so
    # every site participates without having to remember them. Set
    # ``respect_active_campaign = False`` to skip the merge entirely (used
    # by the Campaign site itself and global-catalog sites that opt out).
    _QUERYSET_MIXIN_ATTRS = ("list_mixins", "detail_mixins", "delete_mixins")
    _FORM_MIXIN_ATTRS = ("form_mixins", "create_mixins", "update_mixins")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "respect_active_campaign", True):
            return

        def _prepend_unique(attr, mixin):
            if attr not in cls.__dict__:
                return  # Subclass didn't redefine this tuple → BaseSite default applies.
            current = tuple(cls.__dict__[attr] or ())
            if any(m is mixin for m in current):
                return
            setattr(cls, attr, (mixin,) + current)

        def _append_unique(attr, mixin):
            if attr not in cls.__dict__:
                return
            current = tuple(cls.__dict__[attr] or ())
            if any(m is mixin for m in current):
                return
            setattr(cls, attr, current + (mixin,))

        for attr in cls._QUERYSET_MIXIN_ATTRS:
            _prepend_unique(attr, ActiveCampaignScopeMixin)
        for attr in cls._FORM_MIXIN_ATTRS:
            _prepend_unique(attr, ActiveCampaignFormMixin)
            _append_unique(attr, SaveOptionsMixin)

    def get_urls(self):
        # superadmin registers a ``<pk>/duplicate/`` route unconditionally,
        # which redirects to ``crear/?duplicate=<pk>``. When a site opts out
        # of ``create`` via ``allow_views``, that redirect crashes with
        # ``NoReverseMatch`` and exposes a debug page. Drop the duplicate
        # route in lockstep with ``create`` so read-only sites stay clean.
        urls = super().get_urls()
        if "create" not in self.allow_views:
            urls = [u for u in urls if not (u.name or "").endswith("_duplicate")]
        return urls

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
