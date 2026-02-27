import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def authenticated_user(db):
    return User.objects.create_user(
        username="test@hybel.no",
        email="test@hybel.no",
        password="testpass123",
        first_name="Test",
        last_name="Bruker",
    )


@pytest.fixture
def auth_client(authenticated_user):
    client = APIClient()
    client.force_authenticate(user=authenticated_user)
    return client


@pytest.fixture
def sample_users(db):
    users = []
    for first, last, email in [
        ("Ola", "Nordmann", "ola@hybel.no"),
        ("Kari", "Hansen", "kari@hybel.no"),
        ("Per", "Olsen", "per@hybel.no"),
    ]:
        users.append(
            User.objects.create_user(
                username=email,
                email=email,
                password="testpass123",
                first_name=first,
                last_name=last,
            )
        )
    return users


@pytest.mark.django_db
class TestUserSearchAPI:
    def test_search_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/auth/users/search/?q=Ola")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_search_by_first_name(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=Ola")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["first_name"] == "Ola"

    def test_search_by_last_name(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=Hansen")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["first_name"] == "Kari"

    def test_search_by_full_name(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=Per Olsen")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["email"] == "per@hybel.no"

    def test_search_by_email(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=per@")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_short_query_returns_empty(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=O")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_excludes_self(self, auth_client, authenticated_user):
        response = auth_client.get("/api/auth/users/search/?q=Test")
        assert response.status_code == status.HTTP_200_OK
        assert all(u["id"] != str(authenticated_user.id) for u in response.data)

    def test_returns_correct_fields(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=Ola")
        assert set(response.data[0].keys()) == {"id", "email", "first_name", "last_name"}

    def test_no_results(self, auth_client, sample_users):
        response = auth_client.get("/api/auth/users/search/?q=Nonexistent")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0


@pytest.mark.django_db
class TestCSRFTokenView:
    def test_returns_csrf_token(self):
        client = APIClient()
        response = client.get("/api/auth/csrf/")
        assert response.status_code == status.HTTP_200_OK
        assert "csrfToken" in response.data


@pytest.mark.django_db
class TestLoginView:
    def test_login_success(self, authenticated_user):
        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "test@hybel.no", "password": "testpass123"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "test@hybel.no"

    def test_login_invalid_credentials(self, authenticated_user):
        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"email": "test@hybel.no", "password": "wrongpassword"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Ugyldig" in response.data["detail"]

    def test_login_missing_fields(self):
        client = APIClient()
        response = client.post("/api/auth/login/", {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogoutView:
    def test_logout(self, auth_client):
        response = auth_client.post("/api/auth/logout/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_unauthenticated(self):
        client = APIClient()
        response = client.post("/api/auth/logout/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMeView:
    def test_returns_current_user(self, auth_client, authenticated_user):
        response = auth_client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == authenticated_user.email

    def test_unauthenticated(self):
        client = APIClient()
        response = client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
