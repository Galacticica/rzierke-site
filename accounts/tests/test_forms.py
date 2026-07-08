"""Tests for the accounts app forms."""

import pytest

from accounts.forms import LoginForm, SignupForm

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


class TestLoginForm:
    def test_valid_credentials(self, rf, user):
        form = LoginForm(
            rf.post("/account/login/"),
            data={"email": "user@example.com", "password": "password123"},
        )

        assert form.is_valid()
        assert form.get_user() == user

    def test_invalid_credentials_non_field_error(self, rf, user):
        form = LoginForm(
            rf.post("/account/login/"),
            data={"email": "user@example.com", "password": "wrong-password"},
        )

        assert not form.is_valid()
        assert "Invalid email or password." in form.non_field_errors()


class TestSignupForm:
    def test_valid_data(self):
        form = SignupForm(data=signup_data())

        assert form.is_valid()

    def test_password_mismatch(self):
        form = SignupForm(data=signup_data(confirm_password="different123"))

        assert not form.is_valid()
        assert "Passwords do not match." in form.non_field_errors()

    def test_duplicate_email(self, user):
        form = SignupForm(data=signup_data(email=user.email))

        assert not form.is_valid()
        assert "An account with this email already exists." in form.errors["email"]

    def test_duplicate_email_is_case_insensitive(self, user):
        form = SignupForm(data=signup_data(email="USER@example.com"))

        assert not form.is_valid()
        assert "An account with this email already exists." in form.errors["email"]
