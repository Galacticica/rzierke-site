"""Tests for the accounts app views."""

import pytest
from django.urls import reverse

from accounts.models import AccessRequest, User

pytestmark = pytest.mark.django_db


def signup_data(**overrides):
    data = {
        "email": "new@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "first_name": "New",
        "last_name": "User",
    }
    data.update(overrides)
    return data


class TestLoginView:
    def test_login_page_renders(self, client):
        response = client.get(reverse("login_page"))

        assert response.status_code == 200
        assert response.context["next"] == ""

    def test_next_from_get_in_context(self, client):
        response = client.get(reverse("login_page") + "?next=/ministry/")

        assert response.status_code == 200
        assert response.context["next"] == "/ministry/"

    def test_login_redirects_to_next(self, client, user):
        response = client.post(
            reverse("login_page") + "?next=/ministry/",
            {"email": "user@example.com", "password": "password123"},
        )

        assert response.status_code == 302
        assert response.url == "/ministry/"

    def test_login_without_next_redirects_home(self, client, user):
        response = client.post(
            reverse("login_page"),
            {"email": "user@example.com", "password": "password123"},
        )

        assert response.status_code == 302
        assert response.url == "/"

    def test_authenticated_user_is_redirected(self, auth_client):
        response = auth_client.get(reverse("login_page"))

        assert response.status_code == 302
        assert response.url == "/"


class TestSignupView:
    def test_signup_creates_user_and_logs_in(self, client):
        response = client.post(reverse("signup_page"), signup_data())

        assert response.status_code == 302
        assert response.url == "/"
        user = User.objects.get(email="new@example.com")
        assert user.first_name == "New"
        assert user.last_name == "User"
        assert user.check_password("password123")
        assert response.wsgi_request.user == user

    def test_signup_redirects_to_next(self, client):
        response = client.post(reverse("signup_page") + "?next=/ministry/", signup_data())

        assert response.status_code == 302
        assert response.url == "/ministry/"

    def test_duplicate_email_shows_form_error(self, client, user):
        response = client.post(reverse("signup_page"), signup_data(email=user.email))

        assert response.status_code == 200
        assert response.context["form"].errors["email"] == [
            "An account with this email already exists."
        ]
        assert User.objects.count() == 1


class TestLogoutView:
    def test_logout_redirects_to_next(self, auth_client):
        response = auth_client.get(reverse("logout_page") + "?next=/ministry/")

        assert response.status_code == 302
        assert response.url == "/ministry/"
        assert not response.wsgi_request.user.is_authenticated

    def test_logout_falls_back_to_referer(self, auth_client):
        response = auth_client.get(reverse("logout_page"), HTTP_REFERER="/rzpercussion/")

        assert response.status_code == 302
        assert response.url == "/rzpercussion/"

    def test_logout_without_next_or_referer_redirects_home(self, auth_client):
        response = auth_client.get(reverse("logout_page"))

        assert response.status_code == 302
        assert response.url == "/"


class TestRequestAccessView:
    def test_authenticated_user_uses_account_email(self, auth_client, user):
        response = auth_client.post(
            reverse("request_access"), {"request_type": "lyrics", "email": "other@example.com"}
        )

        assert response.status_code == 200
        access_request = AccessRequest.objects.get()
        assert access_request.email == user.email
        assert access_request.request_type == "lyrics"

    def test_anonymous_user_uses_posted_email(self, client):
        response = client.post(
            reverse("request_access"), {"request_type": "lyrics", "email": "guest@example.com"}
        )

        assert response.status_code == 200
        access_request = AccessRequest.objects.get()
        assert access_request.email == "guest@example.com"

    def test_request_type_defaults_to_performance(self, client):
        client.post(reverse("request_access"), {"email": "guest@example.com"})

        assert AccessRequest.objects.get().request_type == "performance"

    def test_anonymous_without_email_falls_back_to_anonymous(self, client):
        client.post(reverse("request_access"))

        assert AccessRequest.objects.get().email == "anonymous"

    def test_response_contains_confirmation_markup(self, client):
        response = client.post(reverse("request_access"), {"email": "guest@example.com"})

        assert "Request Submitted" in response.content.decode()
