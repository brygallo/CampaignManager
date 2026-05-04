"""Unit tests for ``core.list_mixins.DropdownFilterMixin``."""
from types import SimpleNamespace

import pytest

from core.list_mixins import DropdownFilterMixin, default_lookup_for_type


@pytest.mark.parametrize(
    "field_type, expected",
    [
        ("ForeignKey", "exact"),
        ("OneToOneField", "exact"),
        ("ManyToManyField", "exact"),
        ("BooleanField", "exact"),
        ("CharField", "icontains"),
        ("TextField", "icontains"),
        ("EmailField", "icontains"),
        ("IntegerField", "exact"),
        ("DateField", "gte"),
        ("DateTimeField", "gte"),
        ("UnknownType", "exact"),
    ],
)
def test_default_lookup_for_type(field_type, expected):
    assert default_lookup_for_type(field_type) == expected


class _StubParent:
    """Stand-in for ``superadmin.FilterMixin.get_context_data`` upstream."""

    def __init__(self):
        self._ctx = {"site": {"current_filters": []}}

    def get_context_data(self, **kwargs):
        return dict(self._ctx)


class _MixinUnderTest(DropdownFilterMixin, _StubParent):
    """Compose the mixin with our stub parent so MRO calls go to the stub."""


def _make_request(filters_in_session=None):
    return SimpleNamespace(
        session={"filters": filters_in_session or []},
        GET={},
    )


def _build_view(model, filter_fields, request=None):
    view = _MixinUnderTest()
    view.request = request or _make_request()
    view.site = SimpleNamespace(model=model, filter_fields=filter_fields)
    return view


@pytest.mark.django_db
def test_filter_options_contains_one_entry_per_filter_field():
    from apps.campaigns.models import Position

    view = _build_view(Position, ("scope:Alcance", "is_active"))
    ctx = view.get_context_data()

    options = ctx["site"]["filter_options"]
    assert [opt["name"] for opt in options] == ["scope", "is_active"]


@pytest.mark.django_db
def test_charfield_with_choices_renders_as_select():
    from apps.campaigns.models import Position

    view = _build_view(Position, ("scope",))
    opt = view.get_context_data()["site"]["filter_options"][0]

    assert opt["is_select"] is True
    assert opt["is_date"] is False
    assert opt["default_lookup"] == "exact"
    assert ("nacional", "Nacional") in opt["choices"]


@pytest.mark.django_db
def test_booleanfield_renders_as_select_with_true_false_choices():
    from apps.campaigns.models import Election

    view = _build_view(Election, ("is_active",))
    opt = view.get_context_data()["site"]["filter_options"][0]

    assert opt["field_type"] == "BooleanField"
    assert opt["is_select"] is True
    # FilterService.get_choices returns [(1, "Verdadero"), (0, "False")] for booleans
    values = [v for v, _ in opt["choices"]]
    assert 1 in values and 0 in values


@pytest.mark.django_db
def test_datefield_renders_as_date_range():
    from apps.campaigns.models import Election

    view = _build_view(Election, ("election_date",))
    opt = view.get_context_data()["site"]["filter_options"][0]

    assert opt["is_date"] is True
    assert opt["is_select"] is False
    assert opt["default_lookup"] == "gte"
    assert opt["current_value_gte"] == ""
    assert opt["current_value_lte"] == ""


@pytest.mark.django_db
def test_charfield_without_choices_renders_as_text_input():
    from apps.campaigns.models import Candidate

    view = _build_view(Candidate, ("full_name",))
    opt = view.get_context_data()["site"]["filter_options"][0]

    assert opt["is_text"] is True
    assert opt["is_select"] is False
    assert opt["is_date"] is False
    assert opt["default_lookup"] == "icontains"


@pytest.mark.django_db
def test_current_value_is_pulled_from_session_for_default_lookup():
    from apps.campaigns.models import Position

    request = _make_request(
        filters_in_session=[
            {
                "app": "campaigns",
                "model": "position",
                "params": {"scope__exact": "cantonal"},
                "last_date": "01/01/2026 12:00:00",
            }
        ]
    )
    view = _build_view(Position, ("scope",), request=request)
    opt = view.get_context_data()["site"]["filter_options"][0]

    assert opt["current_value"] == "cantonal"


@pytest.mark.django_db
def test_date_range_pulls_both_bounds_from_session():
    from apps.campaigns.models import Election

    request = _make_request(
        filters_in_session=[
            {
                "app": "campaigns",
                "model": "election",
                "params": {
                    "election_date__gte": "2026-01-01",
                    "election_date__lte": "2026-12-31",
                },
                "last_date": "01/01/2026 12:00:00",
            }
        ]
    )
    view = _build_view(Election, ("election_date",), request=request)
    opt = view.get_context_data()["site"]["filter_options"][0]

    assert opt["current_value_gte"] == "2026-01-01"
    assert opt["current_value_lte"] == "2026-12-31"


@pytest.mark.django_db
def test_filter_session_url_resolves_to_superadmin_session():
    from apps.campaigns.models import Election

    view = _build_view(Election, ("is_active",))
    ctx = view.get_context_data()

    assert ctx["site"]["filter_session_url"].endswith("/campaigns/election/")


@pytest.mark.django_db
def test_no_filter_fields_skips_enrichment():
    from apps.campaigns.models import Election

    view = _MixinUnderTest()
    view.request = _make_request()
    view.site = SimpleNamespace(model=Election, filter_fields=())
    ctx = view.get_context_data()

    assert "filter_options" not in ctx["site"]
