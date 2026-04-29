"""Audit helpers built on top of the ``tracing.Trace`` model.

Ported from ``sim.audit``. Public API:
- ``build_processed_traces(instance, ...)`` returns the list of Trace records
  formatted for ``templates/audit/timeline.html``.
- ``AuditContextMixin`` injects ``processed_traces`` into the context of any
  DetailView.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Iterable

from django.contrib.contenttypes.models import ContentType

MISSING_VALUE = ""
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}


def _build_file_href(raw_value):
    if not raw_value:
        return None
    if isinstance(raw_value, str) and raw_value.startswith(("http://", "https://", "/")):
        return raw_value
    return None


def _is_image_path(raw_value) -> bool:
    if not isinstance(raw_value, str):
        return False
    _, ext = os.path.splitext(raw_value.lower())
    return ext in IMAGE_EXTENSIONS


def default_value_formatter(field_obj, raw_value):
    """Format a raw value pulled from ``Trace.message`` JSON for display."""
    if raw_value in (None, "", []):
        return MISSING_VALUE
    internal = getattr(field_obj, "get_internal_type", lambda: "")()
    if internal == "BooleanField":
        if str(raw_value) in ("1", "True", "true"):
            return "Sí"
        return "No"
    choices = getattr(field_obj, "choices", None)
    if choices:
        mapping = {str(k): v for k, v in choices}
        return mapping.get(str(raw_value), raw_value)
    if internal == "ForeignKey" and isinstance(raw_value, dict):
        return f"ID:{raw_value.get('id')} - {raw_value.get('str', '')}"
    return raw_value


def _format_change(instance, field_name, raw_value, value_formatter):
    field_obj = None
    try:
        field_obj = instance._meta.get_field(field_name)
        verbose = getattr(field_obj, "verbose_name", field_name)
    except Exception:
        verbose = field_name

    value = value_formatter(field_obj, raw_value)
    href = _build_file_href(raw_value) if isinstance(raw_value, str) else None
    is_image = _is_image_path(raw_value)
    is_bool = field_obj is not None and field_obj.get_internal_type() == "BooleanField"
    bool_state = None
    if is_bool:
        bool_state = str(raw_value) in ("1", "True", "true")
    return {
        "verbose_name": verbose,
        "value": value,
        "href": href,
        "is_image": is_image,
        "is_bool": is_bool,
        "bool_state": bool_state,
    }


def build_processed_traces(
    instance,
    *,
    limit: int | None = None,
    exclude_fields: Iterable[str] | None = None,
    value_formatter: Callable | None = None,
):
    """Return the audit trace of ``instance`` as a list of dicts."""
    # Lazy import: tracing is a third-party app and may not be ready at import time.
    from tracing.models import Trace

    formatter = value_formatter or default_value_formatter
    excluded = set(exclude_fields or ())

    ct = ContentType.objects.get_for_model(instance.__class__)
    qs = Trace.objects.filter(content_type=ct, object_id=instance.pk).order_by("-date")
    if limit:
        qs = qs[:limit]

    out = []
    for trace in qs:
        try:
            payload = json.loads(trace.message or "{}")
        except (TypeError, ValueError):
            payload = {}
        changes = []
        for field_name, raw_value in payload.items():
            if field_name in excluded:
                continue
            changes.append(_format_change(instance, field_name, raw_value, formatter))
        out.append({"trace": trace, "changes": changes})
    return out


class AuditContextMixin:
    """Inject ``processed_traces`` into the DetailView context."""

    audit_limit: int | None = None
    audit_exclude_fields: tuple = ()
    audit_value_formatter: Callable | None = None
    audit_context_key: str = "processed_traces"

    def get_audit_instance(self):
        obj = getattr(self, "object", None)
        if obj is None and hasattr(self, "get_object"):
            obj = self.get_object()
        return obj

    def get_audit_kwargs(self):
        return {
            "limit": self.audit_limit,
            "exclude_fields": self.audit_exclude_fields,
            "value_formatter": self.audit_value_formatter,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_audit_instance()
        if instance is not None and getattr(instance, "pk", None):
            context[self.audit_context_key] = build_processed_traces(
                instance, **self.get_audit_kwargs()
            )
        return context
