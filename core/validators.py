"""Validators with user-facing messages localized to Spanish."""
from django.core.validators import FileExtensionValidator as DjangoFileExtensionValidator


class FileExtensionValidator(DjangoFileExtensionValidator):
    message = (
        'La extensión "%(extension)s" no está permitida. '
        "Las extensiones permitidas son: %(allowed_extensions)s."
    )
