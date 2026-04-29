"""Authentication backends.

``EmailOrUsernameBackend`` extends Django's ``ModelBackend`` to allow login
either with the username or with the email address (case-insensitive on the
email side).
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

UserModel = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        try:
            user = UserModel.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except UserModel.DoesNotExist:
            # Run the default password hasher once to mitigate timing attacks.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            user = (
                UserModel.objects.filter(
                    Q(username__iexact=username) | Q(email__iexact=username)
                )
                .order_by("id")
                .first()
            )

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
