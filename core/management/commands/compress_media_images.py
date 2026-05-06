"""Walk ``MEDIA_ROOT`` and compress images already on disk.

Intended as a one-shot pass over existing installations carrying heavy
photos (campaigns, field surveys, territorial ads). For new uploads use
:class:`core.fields.CompressedImageField`, which compresses inline.

Typical usage::

    # Inspect what would happen (no writes)
    python manage.py compress_media_images --dry-run

    # Actually compress, scoped to a subdirectory
    python manage.py compress_media_images --path tenants/macas/territorial_ads

    # Tweak parameters
    python manage.py compress_media_images --max-width 1600 --quality 82

Each file is replaced in place by writing to a temp file and renaming, so
a crash can never leave a half-written image behind. When compression
changes the format (e.g. opaque PNG → JPEG), the on-disk extension is
renamed and we report it; DB rows that store the old path will need to
be updated separately if that ever happens for fields that persist the
full filename.
"""
from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.image_utils import (
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_QUALITY,
    compress_image,
)

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class Command(BaseCommand):
    help = "Comprime imágenes existentes en MEDIA_ROOT para ahorrar espacio en disco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="",
            help=(
                "Subdirectorio relativo a MEDIA_ROOT a procesar. "
                "Vacío = todo el árbol de MEDIA_ROOT."
            ),
        )
        parser.add_argument(
            "--max-width",
            type=int,
            default=DEFAULT_MAX_WIDTH,
            help=f"Ancho máximo (px). Default: {DEFAULT_MAX_WIDTH}.",
        )
        parser.add_argument(
            "--max-height",
            type=int,
            default=DEFAULT_MAX_HEIGHT,
            help=f"Alto máximo (px). Default: {DEFAULT_MAX_HEIGHT}.",
        )
        parser.add_argument(
            "--quality",
            type=int,
            default=DEFAULT_QUALITY,
            help=f"Calidad JPEG/WEBP (1-95). Default: {DEFAULT_QUALITY}.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No escribe archivos; solo muestra el ahorro estimado.",
        )

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        target = (media_root / options["path"]).resolve()
        if not str(target).startswith(str(media_root.resolve())):
            raise CommandError("--path cannot escape MEDIA_ROOT")
        if not target.exists():
            raise CommandError(f"Path not found: {target}")

        dry_run: bool = options["dry_run"]
        max_width: int = options["max_width"]
        max_height: int = options["max_height"]
        quality: int = options["quality"]

        total_files = 0
        total_compressed = 0
        total_saved = 0
        total_renamed = 0

        for path in self._iter_images(target):
            total_files += 1
            try:
                with path.open("rb") as fh:
                    result = compress_image(
                        fh,
                        max_width=max_width,
                        max_height=max_height,
                        quality=quality,
                        name_hint=path.name,
                    )
            except Exception as exc:
                # A single corrupt file shouldn't abort the whole sweep.
                self.stderr.write(self.style.WARNING(f"  ! {path}: {exc}"))
                continue

            if not result.replaced:
                continue

            new_path = path.with_suffix(Path(result.content.name).suffix)
            renamed = new_path != path
            saved = result.saved_bytes

            self.stdout.write(
                f"  - {path.relative_to(media_root)}: "
                f"{_human(result.original_size)} → {_human(result.new_size)} "
                f"(-{_human(saved)})"
                + (f"  [→ {new_path.name}]" if renamed else "")
            )

            if not dry_run:
                self._write_atomically(new_path, result.content.read())
                if renamed:
                    os.remove(path)
                    total_renamed += 1

            total_compressed += 1
            total_saved += saved

        verb = "Se comprimirían" if dry_run else "Comprimidos"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{verb} {total_compressed}/{total_files} archivos. "
                f"Ahorro: {_human(total_saved)}. Renombrados: {total_renamed}."
            )
        )

    @staticmethod
    def _iter_images(root: Path):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                yield path

    @staticmethod
    def _write_atomically(target: Path, data: bytes) -> None:
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)


def _human(n: int) -> str:
    step = 1024.0
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < step:
            return f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} TB"
