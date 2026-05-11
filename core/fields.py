"""Reusable model fields.

- :class:`CompressedImageField` — ``ImageField`` that compresses freshly
  uploaded images before handing them to the storage backend.
- :class:`ColorField` — ``CharField`` for hex colors with built-in
  validation and an HTML5 color picker on auto-built ``ModelForm`` fields.
"""
from __future__ import annotations

import logging

from django.db import models
from django.db.models import ImageField

from .image_utils import (
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_QUALITY,
    OutputFormat,
    compress_image,
)
from .validators import hex_color_validator
from .widgets import ColorPickerWidget

logger = logging.getLogger(__name__)


class ColorField(models.CharField):
    """``CharField`` for hex colors with validation + color picker widget.

    The DB column is identical to ``CharField`` (max_length=7), so swapping
    an existing ``CharField`` declaration to ``ColorField`` does not require
    a schema migration. Validation runs on save / form clean, so existing
    rows are not touched until they are next edited.
    """

    description = "Hex color (#RGB or #RRGGBB)"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 7)
        super().__init__(*args, **kwargs)
        if hex_color_validator not in self.validators:
            self.validators.append(hex_color_validator)

    def formfield(self, **kwargs):
        kwargs.setdefault("widget", ColorPickerWidget)
        return super().formfield(**kwargs)


class CompressedImageField(ImageField):
    """``ImageField`` that compresses new images before saving.

    Per-instance configuration::

        photo = CompressedImageField(
            upload_to="ads/",
            max_width=1600,
            max_height=1600,
            quality=82,
        )

    Compression only runs on *uncommitted* files (those just uploaded
    through a form or freshly assigned in code). Already-stored images
    are not re-compressed when the model is saved unchanged. If the
    pass yields no real saving, the original bytes are kept — useful
    when the user uploads an already-optimized file.
    """

    def __init__(
        self,
        *args,
        max_width: int = DEFAULT_MAX_WIDTH,
        max_height: int = DEFAULT_MAX_HEIGHT,
        quality: int = DEFAULT_QUALITY,
        output_format: OutputFormat | None = None,
        **kwargs,
    ):
        self.max_width = max_width
        self.max_height = max_height
        self.quality = quality
        self.output_format = output_format
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.max_width != DEFAULT_MAX_WIDTH:
            kwargs["max_width"] = self.max_width
        if self.max_height != DEFAULT_MAX_HEIGHT:
            kwargs["max_height"] = self.max_height
        if self.quality != DEFAULT_QUALITY:
            kwargs["quality"] = self.quality
        if self.output_format is not None:
            kwargs["output_format"] = self.output_format
        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        file = getattr(model_instance, self.attname)
        if file and not file._committed:
            self._compress_in_place(file)
        return super().pre_save(model_instance, add)

    def _compress_in_place(self, field_file) -> None:
        """Replace the ``FieldFile`` content/name in place when worthwhile."""
        try:
            result = compress_image(
                field_file.file,
                max_width=self.max_width,
                max_height=self.max_height,
                quality=self.quality,
                output_format=self.output_format,
                name_hint=field_file.name,
            )
        except Exception:
            # Never let compression break the surrounding model save.
            logger.exception("CompressedImageField: error compressing %s", field_file.name)
            return

        if not result.replaced:
            return

        # Swap the underlying file; ``super().pre_save`` will then call
        # ``field_file.save(name, file, save=False)`` with these values
        # and apply ``upload_to``.
        field_file.file = result.content
        field_file.name = result.content.name
