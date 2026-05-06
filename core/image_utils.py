"""Reusable image-compression helpers built on Pillow.

The goal is "near-visually-lossless" output that is much smaller on disk:

* Resize to a bounding box (default 1920x1920) preserving aspect ratio.
* JPEG/WEBP quality of 85 — the usual sweet spot above which file size
  grows quickly without perceptible quality gain.
* Honor EXIF orientation (rotate the pixels) and then drop EXIF metadata.
  Stripping EXIF avoids viewers that ignore the tag rendering rotated
  images sideways, saves bytes, and removes potentially sensitive GPS
  data from user uploads.
* Preserve transparency: images with an alpha channel are written as
  optimized PNG; everything else as progressive JPEG.
* Idempotent: if compression would produce a file larger than the
  original (e.g. user uploaded an already-optimized JPEG), the original
  bytes are kept untouched.

The module knows nothing about the storage backend or the multi-tenant
schema; it operates on file-like objects.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import IO, Literal

from django.core.files.base import ContentFile, File
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)


DEFAULT_MAX_WIDTH = 1920
DEFAULT_MAX_HEIGHT = 1920
DEFAULT_QUALITY = 85

OutputFormat = Literal["JPEG", "PNG", "WEBP"]

_EXTENSION_BY_FORMAT: dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


@dataclass(frozen=True)
class CompressionResult:
    """Outcome of a compression attempt.

    ``content`` is ``None`` when the original was kept (compression did
    not save bytes, or the source was not a valid image).
    """

    content: ContentFile | None
    original_size: int
    new_size: int
    output_format: str | None

    @property
    def replaced(self) -> bool:
        return self.content is not None

    @property
    def saved_bytes(self) -> int:
        return max(self.original_size - self.new_size, 0)


def _has_alpha(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def _flatten_alpha(image: Image.Image) -> Image.Image:
    """Composite an alpha channel onto a white background for JPEG output."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    background = Image.new("RGB", image.size, (255, 255, 255))
    background.paste(image, mask=image.split()[-1])
    return background


def _pick_output_format(image: Image.Image, requested: OutputFormat | None) -> OutputFormat:
    if requested is not None:
        return requested
    return "PNG" if _has_alpha(image) else "JPEG"


def _save_kwargs(output_format: OutputFormat, quality: int) -> dict:
    if output_format == "JPEG":
        return {"quality": quality, "optimize": True, "progressive": True}
    if output_format == "WEBP":
        # method=6 is the slowest/most-effective compression — runs once.
        return {"quality": quality, "method": 6}
    # PNG ignores `quality`; `optimize` shrinks losslessly where possible.
    return {"optimize": True}


def compress_image(
    source: IO[bytes] | File,
    *,
    max_width: int = DEFAULT_MAX_WIDTH,
    max_height: int = DEFAULT_MAX_HEIGHT,
    quality: int = DEFAULT_QUALITY,
    output_format: OutputFormat | None = None,
    name_hint: str | None = None,
) -> CompressionResult:
    """Compress an image and return a :class:`CompressionResult`.

    Parameters
    ----------
    source:
        Any file-like object with ``read``/``seek`` (``UploadedFile``,
        ``FieldFile``, ``BytesIO``, ``open(..., "rb")``, etc.).
    max_width / max_height:
        Bounding box. The image is shrunk preserving aspect; never
        upscaled.
    quality:
        JPEG/WEBP quality in 1-95. 85 is the default sweet spot.
    output_format:
        Force the output format. ``None`` = auto (PNG when there is
        transparency, otherwise JPEG).
    name_hint:
        Original filename, used to build the resulting ``ContentFile``
        name. Falls back to ``source.name`` when omitted.
    """
    if not 1 <= quality <= 95:
        raise ValueError("quality must be between 1 and 95")
    if max_width <= 0 or max_height <= 0:
        raise ValueError("max_width and max_height must be positive")

    name_hint = name_hint or getattr(source, "name", None) or "image"

    try:
        source.seek(0)
    except (AttributeError, OSError):
        # Some streams don't support seek; Pillow will still try.
        pass

    original_size = _safe_size(source)

    try:
        with Image.open(source) as image:
            image.load()
            processed = ImageOps.exif_transpose(image) or image
            chosen_format = _pick_output_format(processed, output_format)

            processed.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            if chosen_format == "JPEG" and processed.mode != "RGB":
                processed = (
                    _flatten_alpha(processed) if _has_alpha(processed) else processed.convert("RGB")
                )
            elif chosen_format == "PNG" and processed.mode not in {"RGBA", "LA", "P", "L"}:
                processed = processed.convert("RGBA")

            buffer = BytesIO()
            processed.save(buffer, format=chosen_format, **_save_kwargs(chosen_format, quality))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("compress_image: cannot process %s: %s", name_hint, exc)
        return CompressionResult(
            content=None, original_size=original_size, new_size=0, output_format=None
        )

    new_bytes = buffer.getvalue()
    new_size = len(new_bytes)

    if original_size and new_size >= original_size:
        # No improvement over the original — keep it.
        return CompressionResult(
            content=None,
            original_size=original_size,
            new_size=new_size,
            output_format=chosen_format,
        )

    new_name = Path(name_hint).stem + _EXTENSION_BY_FORMAT[chosen_format]
    return CompressionResult(
        content=ContentFile(new_bytes, name=new_name),
        original_size=original_size,
        new_size=new_size,
        output_format=chosen_format,
    )


def _safe_size(source: IO[bytes] | File) -> int:
    """Return the source size in bytes, or 0 if it cannot be determined."""
    size = getattr(source, "size", None)
    if isinstance(size, int) and size >= 0:
        return size
    try:
        current = source.tell()
        source.seek(0, 2)
        size = source.tell()
        source.seek(current)
        return int(size)
    except (AttributeError, OSError):
        return 0
