"""End-to-end tests for the authentication flow (login / logout / profile)."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_login_with_username(page, live_server, user, password):
    """A user that types its username + password lands outside /login/."""
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name=username]", user.username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)
    assert "/login/" not in page.url


def test_login_with_email(page, live_server, user, password):
    """The custom backend accepts the user's email in the username field."""
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)
    assert "/login/" not in page.url


def test_login_email_is_case_insensitive(page, live_server, user, password):
    """``EmailOrUsernameBackend`` lowercases the email before lookup."""
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name=username]", user.email.upper())
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)
    assert "/login/" not in page.url


def test_login_wrong_password_keeps_user_on_form(page, live_server, user):
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name=username]", user.username)
    page.fill("input[name=password]", "wrong-password")
    page.click("button[type=submit]")
    # The login view rerenders the form (no redirect). The non-field error
    # should appear in the .alert-danger banner.
    page.wait_for_selector(".alert-danger", timeout=5_000)
    assert "/login/" in page.url


def test_login_inactive_user_rejected(page, live_server, db, password):
    from django.contrib.auth import get_user_model

    inactive = get_user_model().objects.create_user(
        username="ghost",
        email="ghost@example.com",
        password=password,
        is_active=False,
    )
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name=username]", inactive.username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_selector(".alert-danger", timeout=5_000)
    assert "/login/" in page.url


def test_login_honors_next_param(page, live_server, user, password):
    """After a successful login, the ``next`` URL wins over the home page."""
    page.goto(f"{live_server.url}/login/?next=/profile/")
    page.fill("input[name=username]", user.username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/profile/" in url, timeout=10_000)
    assert page.url.endswith("/profile/")


def test_login_ignores_external_next(page, live_server, user, password):
    """``url_has_allowed_host_and_scheme`` must drop external redirects."""
    page.goto(f"{live_server.url}/login/?next=https://evil.example.com/")
    page.fill("input[name=username]", user.username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)
    # Should land on the internal home, not the external URL.
    assert "evil.example.com" not in page.url


def test_authenticated_user_visiting_login_redirects(logged_in_page, live_server):
    """If the session is already authenticated, /login/ bounces them out."""
    logged_in_page.goto(f"{live_server.url}/login/")
    logged_in_page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)
    assert "/login/" not in logged_in_page.url


def test_logout_button_clears_session(logged_in_page, live_server):
    """Submitting the header's logout form lands the user back on /login/.

    The button itself is hidden inside the user-menu dropdown, so this test
    posts the form directly via Playwright's request API to avoid the UI dance
    of opening the menu.
    """
    logged_in_page.goto(f"{live_server.url}/")
    # Grab the CSRF token rendered by the logout form so the POST passes
    # ``CsrfViewMiddleware``.
    token = logged_in_page.locator(
        "form[action$='/logout/'] input[name=csrfmiddlewaretoken]"
    ).first.get_attribute("value")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/logout/",
        form={"csrfmiddlewaretoken": token},
        headers={"Referer": f"{live_server.url}/"},
    )
    assert response.status in (200, 301, 302)
    # After logout, hitting a protected page should bounce to /login/.
    logged_in_page.goto(f"{live_server.url}/")
    logged_in_page.wait_for_url(lambda url: "/login/" in url, timeout=10_000)


def test_remember_me_extends_session(page, live_server, user, password):
    """Checking the "remember me" box sets a long-lived session cookie."""
    page.goto(f"{live_server.url}/login/")
    page.fill("input[name=username]", user.username)
    page.fill("input[name=password]", password)
    page.check("input[name=remember]")
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)
    session_cookies = [c for c in page.context.cookies() if c["name"] == "sessionid"]
    assert session_cookies, "expected a sessionid cookie after login"
    # When remember=on, set_expiry(30 days) gives the cookie an explicit
    # expires/maxAge instead of a session-only lifetime (-1).
    assert session_cookies[0]["expires"] > 0


def test_password_reset_page_renders(page, live_server):
    """Anonymous users can reach the password-reset form."""
    page.goto(f"{live_server.url}/password/reset/")
    assert page.locator("form").count() >= 1
    assert page.locator("input[name=email]").count() == 1


def test_profile_page_requires_login(page, live_server):
    """Hitting /profile/ unauthenticated must redirect to /login/?next=/profile/."""
    page.goto(f"{live_server.url}/profile/")
    page.wait_for_url(lambda url: "/login/" in url, timeout=10_000)
    assert "next=" in page.url


def test_profile_page_shows_user_after_login(logged_in_page, live_server, user):
    logged_in_page.goto(f"{live_server.url}/profile/")
    # The profile page is built around base_form.html — wait for one stable
    # marker and then check the user's first name lands somewhere on the page.
    logged_in_page.wait_for_load_state("networkidle")
    assert user.first_name in logged_in_page.content()
