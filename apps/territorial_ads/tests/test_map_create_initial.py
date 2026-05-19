from types import SimpleNamespace

from core.map_mixins import MapInitialLocationMixin


class _StubParent:
    def get_initial(self):
        return {"campaign": "1"}

    def get_form(self, *args, **kwargs):
        return SimpleNamespace(
            fields={
                "offered_location": SimpleNamespace(
                    widget=SimpleNamespace(attrs={}),
                ),
            }
        )


class _MixinUnderTest(MapInitialLocationMixin, _StubParent):
    pass


def test_map_initial_location_mixin_prefills_offered_coordinates():
    view = _MixinUnderTest()
    view.request = SimpleNamespace(
        GET={
            "offered_latitude": "-2.123456",
            "offered_longitude": "-78.654321",
        }
    )

    assert view.get_initial() == {
        "campaign": "1",
        "offered_latitude": "-2.123456",
        "offered_longitude": "-78.654321",
    }


def test_map_initial_location_mixin_prefills_map_context():
    view = _MixinUnderTest()
    view.request = SimpleNamespace(
        GET={
            "map_zoom": "17",
            "map_layer": "satellite",
        }
    )

    form = view.get_form()

    assert form.fields["offered_location"].widget.attrs == {
        "data-default-zoom": 17,
        "data-default-basemap": "satellite",
    }
