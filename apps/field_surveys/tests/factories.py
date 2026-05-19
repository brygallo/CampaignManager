"""Factory Boy factories for the field_surveys app."""
from __future__ import annotations

from decimal import Decimal

import factory

from apps.authentication.tests.factories import UserFactory
from apps.campaigns.tests.factories import CampaignFactory
from apps.field_surveys.models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyAdvertisingResponse,
    SurveySupportLevel,
)


class SurveySupportLevelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SurveySupportLevel
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"support-{n}")
    name = factory.Sequence(lambda n: f"Nivel apoyo {n}")
    color = "#50cd89"
    order = factory.Sequence(lambda n: n)


class SurveyAdvertisingResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SurveyAdvertisingResponse
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"adresp-{n}")
    name = factory.Sequence(lambda n: f"Respuesta publicidad {n}")
    color = "#3e97ff"
    order = factory.Sequence(lambda n: n)


class AdvertisingTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdvertisingType
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"adtype-{n}")
    name = factory.Sequence(lambda n: f"Tipo publicidad {n}")
    icon = "element-12"
    order = factory.Sequence(lambda n: n)


class FieldSurveyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FieldSurvey

    campaign = factory.SubFactory(CampaignFactory)
    brigadier = factory.SubFactory(UserFactory)
    latitude = Decimal("-2.300000")
    longitude = Decimal("-78.120000")
    gps_accuracy = Decimal("5.00")
    person_name = factory.Faker("name", locale="es_ES")
    person_phone = "0999000111"
    voters_count = 3
    notes = ""


class CompetitorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Competitor

    campaign = factory.SubFactory(CampaignFactory)
    list_number = factory.Sequence(lambda n: str(n + 1))
    political_organization = factory.Sequence(lambda n: f"Org {n}")
    candidate_name = factory.Faker("name", locale="es_ES")
    color = "#f1416c"


class CompetitorAdvertisingDetectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CompetitorAdvertisingDetection

    campaign = factory.SubFactory(CampaignFactory)
    competitor = factory.SubFactory(
        CompetitorFactory, campaign=factory.SelfAttribute("..campaign")
    )
    brigadier = factory.SubFactory(UserFactory)
    advertising_type = factory.SubFactory(AdvertisingTypeFactory)
    latitude = Decimal("-2.301000")
    longitude = Decimal("-78.121000")
    gps_accuracy = Decimal("5.00")
    observation = ""
