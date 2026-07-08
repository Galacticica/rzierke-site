"""Tests for the accounts app models and the custom user manager."""

import pytest

from accounts.models import AccessRequest, User

pytestmark = pytest.mark.django_db


class TestCreateUser:
    def test_empty_email_raises_value_error(self):
        with pytest.raises(ValueError, match="The Email field must be set"):
            User.objects.create_user(email="", password="password123")

    def test_email_domain_is_normalized(self):
        user = User.objects.create_user(email="Foo@EXAMPLE.COM", password="password123")

        # BaseUserManager.normalize_email lowercases only the domain part.
        assert user.email == "Foo@example.com"

    def test_password_is_set_and_usable(self):
        user = User.objects.create_user(email="foo@example.com", password="password123")

        assert user.password != "password123"
        assert user.check_password("password123")
        assert user.has_usable_password()


class TestCreateSuperuser:
    def test_defaults_flags_to_true(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="password123")

        assert admin.is_staff is True
        assert admin.is_superuser is True
        assert admin.is_active is True

    def test_is_staff_false_raises_value_error(self):
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="admin@example.com", password="password123", is_staff=False
            )

    def test_is_superuser_false_raises_value_error(self):
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="admin@example.com", password="password123", is_superuser=False
            )


class TestUserStr:
    def test_str_is_first_and_last_name(self):
        user = User.objects.create_user(
            email="foo@example.com",
            password="password123",
            first_name="Reagan",
            last_name="Zierke",
        )

        assert str(user) == "Reagan Zierke"

    def test_str_with_empty_names_is_empty(self):
        user = User.objects.create_user(email="foo@example.com", password="password123")

        assert str(user) == ""


class TestAccessRequestStr:
    def test_str_contains_type_and_email(self):
        access_request = AccessRequest.objects.create(
            email="foo@example.com", request_type="lyrics"
        )

        assert "lyrics" in str(access_request)
        assert "foo@example.com" in str(access_request)
