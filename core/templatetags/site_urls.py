from django import template
from django.urls import NoReverseMatch

from superadmin import site as superadmin_site
from superadmin.shortcuts import get_urls_of_site

register = template.Library()


@register.simple_tag
def safe_site_url(instance, action):
    if instance is None:
        return ""
    try:
        model_site = superadmin_site.get_modelsite(instance.__class__)
    except Exception:
        return ""
    try:
        urls = get_urls_of_site(model_site, object=instance)
    except NoReverseMatch:
        return ""
    return urls.get(action, "")
