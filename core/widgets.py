"""Generic form widgets used throughout the project."""
from django import forms


class JsonWidget(forms.Textarea):
    """Textarea that signals JSON content to the frontend."""

    def __init__(self, attrs=None):
        defaults = {"class": "form-control font-monospace", "rows": 6}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)


class TextSearchWidget(forms.TextInput):
    """Text input with the CSS hook the frontend uses to attach a search button."""

    def __init__(self, attrs=None):
        defaults = {"class": "form-control text-search-control"}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)
