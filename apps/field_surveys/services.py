"""Dashboard/map data builders for field surveys.

These shape querysets into the chart/filter structures the templates and AJAX
endpoints consume. They hit the database, so they live here (sim's
``services.py`` convention) rather than in ``utils.py``, keeping the views thin.
"""
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.campaigns.querysets import visible_campaign_choices
from apps.field_surveys.constants import COMPETITOR_FALLBACK_COLOR
from apps.field_surveys.models import (
    FieldSurvey,
    SurveyAdvertisingResponse,
    SurveySupportLevel,
)
from apps.field_surveys.utils import (
    advertising_color,
    can_view_all_field_surveys,
    support_color,
)


def build_support_distribution(result_counts):
    """Build the donut input for support levels: ordered list of {code, label, value, color}."""
    rows = [
        ("APOYA", "Apoyan", result_counts.get("support") or 0),
        ("INDECISO", "Indecisos", result_counts.get("undecided") or 0),
        ("NO_APOYA", "No apoyan", result_counts.get("not_support") or 0),
        ("NO_ATENDIO", "No atendieron", result_counts.get("not_attended") or 0),
    ]
    levels_by_code = {
        level.code: level for level in SurveySupportLevel.objects.filter(is_active=True)
    }
    return [
        {
            "code": code,
            "label": label,
            "value": value,
            "color": support_color(levels_by_code.get(code)),
        }
        for code, label, value in rows
    ]


def build_advertising_distribution(result_counts):
    """Build the donut input for advertising acceptance."""
    rows = [
        ("ACEPTA", "Acepta publicidad", result_counts.get("ads_accepted") or 0),
        ("RECHAZA", "Rechaza publicidad", result_counts.get("ads_rejected") or 0),
    ]
    responses_by_code = {
        r.code: r for r in SurveyAdvertisingResponse.objects.filter(is_active=True)
    }
    return [
        {
            "code": code,
            "label": label,
            "value": value,
            "color": advertising_color(responses_by_code.get(code)),
        }
        for code, label, value in rows
    ]


def build_visits_trend(request, surveys):
    """Daily visit counts over the active range (or the last 30 days by default)."""
    today = timezone.localdate()
    date_from = request.GET.get("date_from") or None
    date_to = request.GET.get("date_to") or None
    try:
        start = (
            timezone.datetime.fromisoformat(date_from).date()
            if date_from
            else today - timedelta(days=29)
        )
        end = timezone.datetime.fromisoformat(date_to).date() if date_to else today
    except ValueError:
        start, end = today - timedelta(days=29), today
    if end < start:
        start, end = end, start

    counts = {
        row["day"]: row["count"]
        for row in surveys.annotate(day=TruncDate("created_date"))
        .values("day")
        .annotate(count=Count("id", distinct=True))
        .filter(day__gte=start, day__lte=end)
    }
    labels, values = [], []
    cursor = start
    while cursor <= end:
        labels.append(cursor.strftime("%d %b"))
        values.append(counts.get(cursor, 0))
        cursor += timedelta(days=1)
    return {"labels": labels, "values": values}


def build_competitor_breakdown(competitor_ads):
    """Top competitors by detection count for the small breakdown card."""
    rows = list(
        competitor_ads.values(
            "competitor_id",
            "competitor__political_organization",
            "competitor__color",
        )
        .annotate(detections=Count("id"))
        .order_by("-detections")[:5]
    )
    total = sum(row["detections"] for row in rows) or 1
    for row in rows:
        row["pct"] = int(round((row["detections"] / total) * 100))
        row["color"] = row["competitor__color"] or COMPETITOR_FALLBACK_COLOR
        row["label"] = row["competitor__political_organization"] or "—"
    return rows


def get_filter_context(request):
    campaigns = visible_campaign_choices(request.user)
    if not can_view_all_field_surveys(request.user):
        campaigns = campaigns.filter(field_surveys__brigadier=request.user).distinct()
    active_campaign_id = request.GET.get("campaign") or (
        str(request.active_campaign.pk)
        if getattr(request, "active_campaign", None)
        else ""
    )
    brigadiers_qs = FieldSurvey.objects.all()
    if active_campaign_id:
        brigadiers_qs = brigadiers_qs.filter(campaign_id=active_campaign_id)
    return {
        "active_campaign_filter_id": active_campaign_id,
        "filter_campaigns": campaigns,
        "filter_support_levels": SurveySupportLevel.objects.filter(
            is_active=True
        ).order_by("order", "name"),
        "filter_advertising_responses": SurveyAdvertisingResponse.objects.filter(
            is_active=True
        ).order_by("order", "name"),
        "filter_brigadiers": brigadiers_qs.values(
            "brigadier_id",
            "brigadier__username",
            "brigadier__first_name",
            "brigadier__last_name",
        )
        .distinct()
        .order_by("brigadier__first_name", "brigadier__last_name", "brigadier__username"),
    }
