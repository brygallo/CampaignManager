"""Template filters for reading Django model `_meta` attributes.

Django templates forbid accessing names that start with an underscore, so
`model._meta.verbose_name_plural` cannot be expressed inline. These filters
bridge that gap for read-only display use cases (e.g. inline formset titles).
"""
from django.apps import apps
from django import template
from django.db.models import Model

register = template.Library()


def _model_from(value):
    if value is None:
        return None
    if isinstance(value, type) and issubclass(value, Model):
        return value
    if isinstance(value, Model):
        return value.__class__
    if isinstance(value, dict):
        app_name = value.get("app_name") or value.get("app_label")
        model_name = value.get("model_name")
        if app_name and model_name:
            try:
                return apps.get_model(app_name, model_name)
            except LookupError:
                return None
        return None
    meta_model = getattr(getattr(value, "_meta", None), "model", None)
    if isinstance(meta_model, type) and issubclass(meta_model, Model):
        return meta_model
    model = getattr(value, "model", None)
    if isinstance(model, type) and issubclass(model, Model):
        return model
    return None


@register.filter
def verbose_name(value):
    model = _model_from(value)
    return model._meta.verbose_name if model else ""


@register.filter
def verbose_name_plural(value):
    model = _model_from(value)
    return model._meta.verbose_name_plural if model else ""


@register.filter
def is_wide_form_widget(bound_field):
    """Return True when a form field should span the full form row."""
    widget = getattr(getattr(bound_field, "field", None), "widget", None)
    widget_class_name = widget.__class__.__name__ if widget else ""
    return widget_class_name in {
        "Textarea",
        "CKEditorWidget",
        "CKEditor5Widget",
        "ClearableFileInput",
        "FileInput",
        "LeafletMapWidget",
    }
