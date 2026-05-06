"""Tests for the generic image-compression utilities and field."""
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.fields import CompressedImageField
from core.image_utils import compress_image


def _make_image(
    size: tuple[int, int] = (3000, 2000),
    color: tuple[int, int, int] = (255, 0, 0),
    fmt: str = "JPEG",
    mode: str = "RGB",
    noisy: bool = True,
) -> BytesIO:
    """Build an in-memory test image.

    By default we sprinkle pixel noise over the image so re-encoding has
    real content to compress. Without noise (``noisy=False``) the image
    is a flat color, which JPEG handles poorly — useful only when the
    test wants to exercise the "no savings" branch.
    """
    img = Image.new(mode, size, color)
    if noisy:
        import random as _random

        rng = _random.Random(0xC0FFEE)
        pixels = img.load()
        sample_count = (size[0] * size[1]) // 4
        for _ in range(sample_count):
            x = rng.randrange(size[0])
            y = rng.randrange(size[1])
            r = rng.randrange(256)
            g = rng.randrange(256)
            b = rng.randrange(256)
            if mode == "RGBA":
                pixels[x, y] = (r, g, b, rng.randrange(256))
            elif mode == "RGB":
                pixels[x, y] = (r, g, b)
            else:
                pixels[x, y] = r
    buf = BytesIO()
    save_kwargs = {"quality": 95} if fmt == "JPEG" else {}
    img.save(buf, format=fmt, **save_kwargs)
    buf.seek(0)
    buf.name = f"test.{fmt.lower()}"
    return buf


def test_compress_image_resizes_within_bounding_box():
    src = _make_image(size=(4000, 3000))
    original_size = len(src.getvalue())

    result = compress_image(src, max_width=1920, max_height=1920)

    assert result.replaced is True
    assert result.new_size < original_size

    # Pillow shrinks aspect-correct: width hits the cap first here.
    out = Image.open(result.content)
    assert out.width <= 1920
    assert out.height <= 1920
    assert out.width == 1920
    assert out.height == 1440  # 4000:3000 ratio applied to width 1920


def test_compress_image_keeps_jpeg_for_opaque_input():
    src = _make_image(size=(2000, 2000), fmt="PNG", mode="RGB")
    result = compress_image(src)

    assert result.replaced
    assert result.output_format == "JPEG"
    assert result.content.name.endswith(".jpg")


def test_compress_image_preserves_transparency_with_png():
    src = _make_image(size=(800, 600), fmt="PNG", mode="RGBA", color=(255, 0, 0))
    result = compress_image(src)

    assert result.replaced
    assert result.output_format == "PNG"
    assert result.content.name.endswith(".png")

    out = Image.open(result.content)
    assert out.mode in {"RGBA", "LA", "P"}


def test_compress_image_returns_no_replacement_when_no_savings():
    # A flat-color image fits JPEG poorly: re-encoding makes it bigger,
    # so the helper must keep the original.
    src = _make_image(size=(2000, 2000), fmt="PNG", mode="RGB", noisy=False)
    result = compress_image(src, max_width=1920, max_height=1920)

    assert result.replaced is False
    assert result.content is None


def test_compress_image_handles_invalid_input_gracefully():
    bogus = BytesIO(b"not an image at all")
    bogus.name = "broken.jpg"

    result = compress_image(bogus)

    assert result.replaced is False
    assert result.content is None
    assert result.output_format is None


def test_compress_image_validates_quality_bounds():
    src = _make_image()
    with pytest.raises(ValueError):
        compress_image(src, quality=120)
    with pytest.raises(ValueError):
        compress_image(src, quality=0)


def test_compress_image_validates_dimension_bounds():
    src = _make_image()
    with pytest.raises(ValueError):
        compress_image(src, max_width=0)
    with pytest.raises(ValueError):
        compress_image(src, max_height=-10)


def test_compressed_image_field_deconstruct_round_trip():
    field = CompressedImageField(
        upload_to="x/", max_width=1600, max_height=1200, quality=80
    )
    _name, _path, _args, kwargs = field.deconstruct()

    assert kwargs["max_width"] == 1600
    assert kwargs["max_height"] == 1200
    assert kwargs["quality"] == 80
    # Defaults are NOT serialized — keeps migrations clean.
    assert "output_format" not in kwargs


def test_compressed_image_field_deconstruct_skips_defaults():
    field = CompressedImageField(upload_to="x/")
    *_, kwargs = field.deconstruct()
    assert "max_width" not in kwargs
    assert "max_height" not in kwargs
    assert "quality" not in kwargs
    assert "output_format" not in kwargs


def test_compressed_image_field_compresses_uncommitted_file_in_place():
    field = CompressedImageField(upload_to="x/", max_width=800, max_height=800)

    src = _make_image(size=(3000, 2000))
    original_bytes = src.getvalue()
    upload = SimpleUploadedFile("photo.jpg", original_bytes, content_type="image/jpeg")

    # Simulate a freshly-assigned FieldFile by mimicking what Django's
    # FileDescriptor does on assignment, without touching the database.
    class _Stub:
        name = upload.name
        size = upload.size
        _committed = False

        def __init__(self, raw):
            self.file = raw

    stub = _Stub(upload)

    field._compress_in_place(stub)

    assert stub.name.endswith(".jpg")
    new_size = len(stub.file.read())
    assert new_size < len(original_bytes)
    stub.file.seek(0)

    out = Image.open(stub.file)
    assert max(out.size) <= 800
