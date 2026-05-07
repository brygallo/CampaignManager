"""Sim templatetags"""

# Django
from django import template
from django.shortcuts import reverse

# Third party integration
from superadmin import site
from superadmin.shortcuts import get_slug_or_pk, get_urls_of_site
from superadmin.templatetags.superadmin_utils import site_url

register = template.Library()


@register.simple_tag()
def insoles_detail(instance):
    model_site = site.get_modelsite(instance.__class__)
    app_name = instance.__class__._meta.app_label
    model_name = instance._meta.model.__name__
    raw_slug_or_pk = get_slug_or_pk(instance, slug_field=model_site.slug_field)
    slug_or_pk = ""
    slug = ""
    for key, value in raw_slug_or_pk.items():
        slug = value
        slug_or_pk = key
    return reverse("insoles_detail", args=(app_name, model_name, slug, slug_or_pk))


@register.simple_tag()
def insoles_edit(instance):
    model_site = site.get_modelsite(instance.__class__)
    app_name = instance.__class__._meta.app_label
    model_name = instance._meta.model.__name__
    raw_slug_or_pk = get_slug_or_pk(instance, slug_field=model_site.slug_field)
    slug_or_pk = ""
    slug = ""
    for key, value in raw_slug_or_pk.items():
        slug = value
        slug_or_pk = key
    return reverse("insoles_form_edit", args=(app_name, model_name, slug, slug_or_pk))


@register.simple_tag()
def insoles_create_url(instance):
    # TODO: not yet implemented; return empty string to avoid breaking templates.
    return ""


@register.simple_tag()
def render_insoles_detail(instance):
    is_registered = site.is_registered(instance.__class__)
    data = {
        "has_detail_url": False,
        "has_detail_fields": False,
    }
    if is_registered:
        model_site = site.get_modelsite(instance.__class__)
        urls = get_urls_of_site(model_site, object=instance)
        if "detail" in urls:
            data = {
                "has_detail_url": True,
                "has_detail_fields": model_site.detail_fields,
                "insoles_url": insoles_detail(instance),
                "insoles_form_edit": insoles_edit(instance),
                "site_url": urls["detail"],
            }
    return data


@register.simple_tag()
def has_detail_url(instance):
    try:
        site_url(instance, "detail")
        return True
    except Exception:
        return False
