"""Template filters for reading Django model `_meta` attributes.

Django templates forbid accessing names that start with an underscore, so
`model._meta.verbose_name_plural` cannot be expressed inline. These filters
bridge that gap for read-only display use cases (e.g. inline formset titles).
"""
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
