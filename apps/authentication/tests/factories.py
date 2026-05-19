"""Factory Boy factories for the authentication app."""
from __future__ import annotations

import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Active, non-staff Django user with a reproducible password."""

    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name", locale="es_ES")
    last_name = factory.Faker("last_name", locale="es_ES")
    is_active = True
    is_staff = False
    is_superuser = False
    password = factory.PostGenerationMethodCall("set_password", "Sup3rS3cret!")


class StaffUserFactory(UserFactory):
    is_staff = True


class SuperUserFactory(UserFactory):
    is_staff = True
    is_superuser = True
