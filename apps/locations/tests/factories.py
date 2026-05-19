"""Factory Boy factories for the locations app."""
from __future__ import annotations

import factory

from apps.locations.models import Canton, Parish, Province, Sector


class ProvinceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Province
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"P{n:02d}")
    name = factory.Sequence(lambda n: f"Provincia {n}")


class CantonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Canton
        django_get_or_create = ("code",)

    province = factory.SubFactory(ProvinceFactory)
    code = factory.Sequence(lambda n: f"C{n:03d}")
    name = factory.Sequence(lambda n: f"Cantón {n}")


class ParishFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Parish
        django_get_or_create = ("code",)

    canton = factory.SubFactory(CantonFactory)
    code = factory.Sequence(lambda n: f"PR{n:04d}")
    name = factory.Sequence(lambda n: f"Parroquia {n}")
    kind = "URBANA"


class SectorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sector

    parish = factory.SubFactory(ParishFactory)
    name = factory.Sequence(lambda n: f"Sector {n}")
