"""Factory Boy factories for the political_agenda app."""
from __future__ import annotations

from datetime import timedelta

import factory
from django.utils import timezone

from apps.authentication.tests.factories import UserFactory
from apps.campaigns.tests.factories import CampaignFactory
from apps.political_agenda.models import (
    AgendaEventType,
    PoliticalAgendaEvent,
    PoliticalAgendaRequest,
)


class AgendaEventTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AgendaEventType
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"evtype-{n}")
    name = factory.Sequence(lambda n: f"Tipo evento {n}")
    color = "#3e97ff"
    icon = "calendar-tick"
    order = factory.Sequence(lambda n: n)


class PoliticalAgendaRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PoliticalAgendaRequest

    campaign = factory.SubFactory(CampaignFactory)
    title = factory.Sequence(lambda n: f"Solicitud {n}")
    event_type = factory.SubFactory(AgendaEventTypeFactory)
    priority = "MEDIA"
    requester_name = factory.Faker("name", locale="es_ES")
    requester_phone = "0999000222"
    proposed_start_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=7)
    )
    proposed_end_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=7, hours=2)
    )


class PoliticalAgendaEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PoliticalAgendaEvent

    campaign = factory.SubFactory(CampaignFactory)
    title = factory.Sequence(lambda n: f"Evento {n}")
    event_type = factory.SubFactory(AgendaEventTypeFactory)
    start_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=3))
    end_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=3, hours=2)
    )
    address = "Centro de Macas"
    is_public = True
    organizer_name = "Equipo de campaña"
    organizer_phone = "0999000333"
    responsible = factory.SubFactory(UserFactory)
    expected_attendees = 50
