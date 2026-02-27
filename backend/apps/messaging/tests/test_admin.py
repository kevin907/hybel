import pytest
from django.contrib.admin.sites import site as admin_site
from django.test import Client

from apps.messaging.models import (
    Attachment,
    Conversation,
    ConversationParticipant,
    Delegation,
    Message,
    ReadState,
)
from apps.users.models import User


@pytest.mark.django_db
class TestMessagingAdminRegistered:
    """Verify all messaging models are registered in the admin."""

    def test_conversation_registered(self):
        assert Conversation in admin_site._registry

    def test_participant_registered(self):
        assert ConversationParticipant in admin_site._registry

    def test_message_registered(self):
        assert Message in admin_site._registry

    def test_attachment_registered(self):
        assert Attachment in admin_site._registry

    def test_read_state_registered(self):
        assert ReadState in admin_site._registry

    def test_delegation_registered(self):
        assert Delegation in admin_site._registry


@pytest.mark.django_db
class TestMessagingAdminViews:
    """Verify admin list views load without error."""

    @pytest.fixture
    def admin_client(self, db):
        admin = User.objects.create_superuser(
            email="admin@test.no", password="admin123", username="admin@test.no"
        )
        client = Client()
        client.force_login(admin)
        return client

    def test_conversation_changelist(self, admin_client):
        response = admin_client.get("/admin/messaging/conversation/")
        assert response.status_code == 200

    def test_message_changelist(self, admin_client):
        response = admin_client.get("/admin/messaging/message/")
        assert response.status_code == 200
