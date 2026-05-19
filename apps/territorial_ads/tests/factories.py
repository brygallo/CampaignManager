"""Factory Boy factories for the territorial_ads app."""
from __future__ import annotations

from decimal import Decimal

import factory

from apps.authentication.tests.factories import UserFactory
from apps.campaigns.tests.factories import CampaignFactory
from apps.field_surveys.tests.factories import AdvertisingTypeFactory
from apps.territorial_ads.models import (
    AdvertisingCostType,
    AdvertisingRefusal,
    PhysicalAdvertisement,
)


class AdvertisingCostTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdvertisingCostType
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"costtype-{n}")
    name = factory.Sequence(lambda n: f"Costo {n}")
    order = factory.Sequence(lambda n: n)
    requires_amount = False


class PhysicalAdvertisementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PhysicalAdvertisement

    campaign = factory.SubFactory(CampaignFactory)
    advertisement_type = factory.SubFactory(AdvertisingTypeFactory)
    quantity = 1
    owner_name = factory.Faker("name", locale="es_ES")
    owner_phone = "0999000444"
    cost_type = factory.SubFactory(AdvertisingCostTypeFactory)
    address = "Av. Macas Norte, frente al parque"
    offered_latitude = Decimal("-2.302000")
    offered_longitude = Decimal("-78.123000")


class AdvertisingRefusalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdvertisingRefusal

    campaign = factory.SubFactory(CampaignFactory)
    reason = "No autorizan la instalación"
    owner_reference = "Local cerrado"
    latitude = Decimal("-2.305000")
    longitude = Decimal("-78.124000")
    reported_by = factory.SubFactory(UserFactory)
