"""Pure helpers for political agenda: detail URLs and date parsing.

Mirrors sim's ``utils.py`` convention — small, reusable, side-effect-free
functions.
"""
from datetime import datetime

from django.urls import reverse
from django.utils.dateparse import parse_datetime


def event_detail_url(pk):
    return reverse("site:political_agenda_politicalagendaevent_", kwargs={"pk": pk})


def parse_iso(raw):
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is not None:
        return parsed
    # FullCalendar sometimes sends a bare YYYY-MM-DD.
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
