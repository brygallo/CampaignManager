"""Generic project mixins."""


class ExtraContextMixin:
    """Allow declarative extra context on a view via ``extra_context = {...}``."""

    extra_context: dict | None = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.extra_context or {})
        return context
