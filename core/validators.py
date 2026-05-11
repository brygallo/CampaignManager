"""Validators with user-facing messages localized to Spanish."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator as DjangoFileExtensionValidator
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)


class FileExtensionValidator(DjangoFileExtensionValidator):
    message = (
        'La extensión "%(extension)s" no está permitida. '
        "Las extensiones permitidas son: %(allowed_extensions)s."
    )


hex_color_validator = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    message="Usa formato hexadecimal: #RGB o #RRGGBB.",
    code="invalid_hex_color",
)

# Reusable bounds for geographic coordinate fields. Plug into a model field
# via ``validators=[*LATITUDE_VALIDATORS]`` (or longitude). Keep the spread
# so future additions don't replace the list silently.
LATITUDE_VALIDATORS = (
    MinValueValidator(-90, message="La latitud debe estar entre -90 y 90."),
    MaxValueValidator(90, message="La latitud debe estar entre -90 y 90."),
)
LONGITUDE_VALIDATORS = (
    MinValueValidator(-180, message="La longitud debe estar entre -180 y 180."),
    MaxValueValidator(180, message="La longitud debe estar entre -180 y 180."),
)


# Keenicons icon names follow lowercase-with-dashes (e.g. "calendar-tick"). A
# loose pattern catches typos like uppercase or accidental whitespace without
# requiring us to enumerate the whole iconset.
icon_name_validator = RegexValidator(
    regex=r"^[a-z0-9][a-z0-9-]*$",
    message=(
        "Usa el nombre del ícono Keenicons en minúsculas, sin el prefijo "
        "'ki-' (ej. 'calendar-tick')."
    ),
    code="invalid_icon_name",
)


# Election dates further than this many years in the future almost always
# indicate a typo (e.g. 2099 instead of 2029). Picked to comfortably cover
# any real-world electoral horizon while still rejecting absurd values.
ELECTION_DATE_MAX_YEARS_AHEAD = 10


def reasonable_future_date_validator(value):
    """Reject election dates more than ``ELECTION_DATE_MAX_YEARS_AHEAD`` ahead.

    Past dates are intentionally allowed: archived campaigns reference the
    election that triggered them, so the field needs to keep accepting old
    values long after the vote happened.
    """
    if value is None:
        return
    horizon = date.today() + timedelta(days=365 * ELECTION_DATE_MAX_YEARS_AHEAD)
    if value > horizon:
        raise ValidationError(
            f"La fecha no puede superar los {ELECTION_DATE_MAX_YEARS_AHEAD} años "
            "desde hoy. Verifica el año ingresado.",
            code="future_date_too_far",
        )
