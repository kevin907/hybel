import uuid

import pytest
from django.db import IntegrityError

from apps.users.models import User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = User.objects.create_user(
            username="test@hybel.no",
            email="test@hybel.no",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        assert user.email == "test@hybel.no"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.check_password("testpass123")

    def test_uuid_primary_key(self):
        user = User.objects.create_user(
            username="uuid@hybel.no",
            email="uuid@hybel.no",
            password="testpass123",
        )
        assert isinstance(user.id, uuid.UUID)

    def test_email_unique(self):
        User.objects.create_user(
            username="dup1",
            email="dup@hybel.no",
            password="testpass123",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username="dup2",
                email="dup@hybel.no",
                password="testpass123",
            )

    def test_str_returns_full_name(self):
        user = User(first_name="Ola", last_name="Nordmann")
        assert str(user) == "Ola Nordmann"

    def test_username_field_is_email(self):
        assert User.USERNAME_FIELD == "email"

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@hybel.no",
            password="adminpass",
        )
        assert admin.is_superuser
        assert admin.is_staff
