"""BaseForm with declarative fieldset support.

Adapted from ``superadmin.forms.ModelForm``: lets you describe a Bootstrap
column layout via tuples / dicts in ``Meta.fieldsets``.
"""
from django import forms
from django.apps import apps
from django.forms.forms import DeclarativeFieldsMetaclass
from django_select2 import forms as s2forms


class BaseForm(forms.BaseForm, metaclass=DeclarativeFieldsMetaclass):
    """Non-Model form with fieldsets."""

    @staticmethod
    def parse(fieldset):
        if not isinstance(fieldset, (list, tuple)):
            fieldset = (fieldset,)
        rows = []
        for row in fieldset:
            if isinstance(row, str):
                row = (row,)
            cols = max(1, 12 // max(len(row), 1))
            rows.append({"bs_cols": cols, "fields": list(row)})
        return rows

    def get_fieldsets(self):
        meta = getattr(self, "Meta", None)
        fieldsets = getattr(meta, "fieldsets", None)
        if not fieldsets:
            return []
        result = []
        if isinstance(fieldsets, dict):
            for title, content in fieldsets.items():
                result.append({"title": title, "fieldset": self.parse(content)})
        else:
            result.append({"title": "", "fieldset": self.parse(fieldsets)})
        # Resolve field names into BoundField instances.
        for section in result:
            for row in section["fieldset"]:
                row["fields"] = [self[name] for name in row["fields"] if name in self.fields]
        return result

    def has_fieldsets(self):
        meta = getattr(self, "Meta", None)
        return bool(getattr(meta, "fieldsets", None))


def _resolve_model_meta(model):
    if isinstance(model, str):
        app_label, model_name = model.split(".", 1)
        model_class = apps.get_model(app_label, model_name)
    else:
        model_class = model
    return model_class._meta.app_label, model_class._meta.object_name


def select2_attrs(model, attrs=None, allow_create=True):
    defaults = {
        "class": "django-select2 form-select form-select-solid",
        "data-minimum-input-length": 0,
    }
    if allow_create:
        app_label, object_name = _resolve_model_meta(model)
        defaults.update(
            {
                "data-app": app_label,
                "data-model": object_name,
            }
        )
    if attrs:
        if attrs.get("class"):
            attrs = {**attrs, "class": f"{defaults['class']} {attrs['class']}"}
        defaults.update(attrs)
    return defaults


def model_select2_widget(
    model,
    search_fields,
    *,
    multiple=False,
    max_results=100,
    dependent_fields=None,
    attrs=None,
    allow_create=True,
):
    widget_class = (
        s2forms.ModelSelect2MultipleWidget
        if multiple
        else s2forms.ModelSelect2Widget
    )
    kwargs = {
        "model": model,
        "search_fields": search_fields,
        "max_results": max_results,
        "attrs": select2_attrs(model, attrs=attrs, allow_create=allow_create),
    }
    if dependent_fields:
        kwargs["dependent_fields"] = dependent_fields
    return widget_class(**kwargs)


class Select2ModelFormMixin:
    """Apply ModelSelect2 widgets from a declarative ``Meta.select2_fields`` map."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, config in self.get_select2_fields().items():
            if field_name not in self.fields:
                continue
            field = self.fields[field_name]
            field.widget = model_select2_widget(**config)
            # Re-bind the widget's ``choices`` to the field's iterator. Without
            # this step ``ModelSelect2Widget.optgroups()`` cannot resolve the
            # initial value on edit views — the form renders ``<select>`` with
            # only the empty placeholder option, forcing the user to reassign
            # the FK manually (BUG-CAMP-02). The choices iterator is what
            # ``Field.__init__`` originally hands the widget, so we restore
            # that pairing here.
            field.widget.choices = field.choices

    def get_select2_fields(self):
        meta = getattr(self, "Meta", None)
        return getattr(meta, "select2_fields", {})
