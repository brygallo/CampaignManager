from types import SimpleNamespace

from core.list_mixins import WorkflowStateFilterMixin


class _StubParent:
    def get_queryset(self):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        return {}


class _MixinUnderTest(WorkflowStateFilterMixin, _StubParent):
    pass


def test_state_filter_visible_path_includes_tenant_prefix():
    view = _MixinUnderTest()
    view.request = SimpleNamespace(
        path="/publicidad-territorial/publicidad-fisica/",
        tenant_path_prefix="/pachackutik",
    )

    assert (
        view._request_visible_path()
        == "/pachackutik/publicidad-territorial/publicidad-fisica/"
    )


def test_state_filter_visible_path_does_not_double_prefix():
    view = _MixinUnderTest()
    view.request = SimpleNamespace(
        path="/pachackutik/publicidad-territorial/publicidad-fisica/",
        tenant_path_prefix="/pachackutik",
    )

    assert (
        view._request_visible_path()
        == "/pachackutik/publicidad-territorial/publicidad-fisica/"
    )
