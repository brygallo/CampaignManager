"""BaseForm with declarative fieldset support.

Adapted from ``superadmin.forms.ModelForm``: lets you describe a Bootstrap
column layout via tuples / dicts in ``Meta.fieldsets``.
"""
from django import forms
from django.forms.forms import DeclarativeFieldsMetaclass


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
