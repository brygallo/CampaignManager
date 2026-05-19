"""Factory Boy factories for the campaigns app."""
from __future__ import annotations

from datetime import date, timedelta

import factory

from apps.campaigns.models import (
    Campaign,
    Candidate,
    Election,
    PoliticalMovement,
    Position,
)


class ElectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Election
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Elecciones {2026 + n}")
    election_date = factory.LazyFunction(lambda: date.today() + timedelta(days=180))
    description = ""


class PoliticalMovementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PoliticalMovement
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Movimiento {n}")
    acronym = factory.Sequence(lambda n: f"M{n:02d}")
    list_number = factory.Sequence(lambda n: str(n))
    color = "#3e97ff"


class PositionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Position
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Cargo {n}")
    scope = "cantonal"


class CandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Candidate

    full_name = factory.Faker("name", locale="es_ES")
    identification = factory.Sequence(lambda n: f"170000{n:04d}")
    email = factory.Faker("email")
    phone = "0999999999"
    bio = ""


class CampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Campaign

    name = factory.Sequence(lambda n: f"Campaña {n}")
    election = factory.SubFactory(ElectionFactory)
    candidate = factory.SubFactory(CandidateFactory)
    movement = factory.SubFactory(PoliticalMovementFactory)
    position = factory.SubFactory(PositionFactory)
    start_date = factory.LazyFunction(lambda: date.today() - timedelta(days=30))
    end_date = factory.LazyFunction(lambda: date.today() + timedelta(days=180))
    description = ""
    is_default = False
