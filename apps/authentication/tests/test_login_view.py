from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase

from apps.authentication.views import login_view
from tracing.middleware import TracingMiddleware


class LoginViewTracingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(
            username="admin",
            is_authenticated=True,
        )

    def _build_request(self, data):
        request = self.factory.post("/login/", data)
        request.session = SessionStore()
        request.user = AnonymousUser()
        return request

    def test_login_sets_tracing_user_before_auth_login(self):
        request = self._build_request({"username": "admin", "password": "secret123"})

        TracingMiddleware.thread_local.user = None

        fake_form = SimpleNamespace(
            is_valid=lambda: True,
            get_user=lambda: self.user,
        )

        def fake_auth_login(request_obj, user):
            self.assertEqual(TracingMiddleware.thread_local.user, user)

        with patch(
            "apps.authentication.views.EmailOrUsernameAuthenticationForm",
            return_value=fake_form,
        ), patch(
            "apps.authentication.views.auth_login",
            side_effect=fake_auth_login,
        ), patch(
            "apps.authentication.views.redirect",
            side_effect=lambda to: HttpResponseRedirect(to),
        ):
            response = login_view.__wrapped__.__wrapped__(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
