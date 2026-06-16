"""Pure helpers for field surveys: permission checks, scoped querysets, detail
URLs and marker-color resolution.

Mirrors sim's ``utils.py`` convention — small, reusable, side-effect-free
functions (the queryset builder only composes a lazy ``QuerySet``).
"""
from django.urls import reverse

from apps.field_surveys.constants import (
    ADVERTISING_FALLBACK_COLORS,
    DEFAULT_VISIT_COLOR,
    SUPPORT_FALLBACK_COLORS,
)
from apps.field_surveys.models import FieldSurvey


def can_view_all_field_surveys(user):
    return (
        user.is_superuser
        or user.is_staff
        or user.has_perm("field_surveys.view_all_fieldsurvey")
    )


def fieldsurvey_queryset_for_user(user):
    queryset = (
        FieldSurvey.objects.select_related(
            "campaign",
            "brigadier",
            "created_by",
            "support_level",
            "advertising_response",
        )
        .prefetch_related("competitor_advertising_detections")
        .all()
    )
    if not can_view_all_field_surveys(user):
        queryset = queryset.filter(brigadier=user)
    return queryset


def fieldsurvey_list_url():
    return reverse("site:field_surveys_fieldsurvey_listar")


def fieldsurvey_detail_url(pk):
    return reverse("site:field_surveys_fieldsurvey_", kwargs={"pk": pk})


def competitor_detection_detail_url(pk):
    return reverse(
        "site:field_surveys_competitoradvertisingdetection_", kwargs={"pk": pk}
    )


def support_color(level):
    if not level:
        return DEFAULT_VISIT_COLOR
    return level.color or SUPPORT_FALLBACK_COLORS.get(level.code, DEFAULT_VISIT_COLOR)


def advertising_color(response):
    if not response:
        return DEFAULT_VISIT_COLOR
    return response.color or ADVERTISING_FALLBACK_COLORS.get(
        response.code, DEFAULT_VISIT_COLOR
    )
