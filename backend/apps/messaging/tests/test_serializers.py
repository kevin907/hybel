import pytest
from rest_framework.test import APIRequestFactory

from apps.messaging.serializers import ConversationListSerializer, MessageSerializer

from .conftest import (
    InternalCommentFactory,
    MessageFactory,
    ReadStateFactory,
)


@pytest.fixture
def request_factory():
    return APIRequestFactory()


@pytest.mark.django_db
class TestConversationListSerializer:
    def test_includes_unread_count(
        self, conversation_with_participants, tenant_user, request_factory
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=3)

        request = request_factory.get("/")
        request.user = tenant_user

        serializer = ConversationListSerializer(conv, context={"request": request})
        assert serializer.data["unread_count"] == 3

    def test_last_message_excludes_internal_for_tenant(
        self,
        conversation_with_participants,
        tenant_user,
        landlord_user,
        request_factory,
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Synlig melding")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Intern notat")

        request = request_factory.get("/")
        request.user = tenant_user

        serializer = ConversationListSerializer(conv, context={"request": request})
        last_msg = serializer.data["last_message"]
        assert last_msg is not None
        assert "Synlig" in last_msg["content"]
        assert last_msg["is_internal"] is False


@pytest.mark.django_db
class TestMessageSerializer:
    def test_includes_sender_detail(
        self, conversation_with_participants, tenant_user, request_factory
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        request = request_factory.get("/")
        request.user = tenant_user

        serializer = MessageSerializer(msg, context={"request": request})
        assert serializer.data["sender"]["id"] == str(tenant_user.id)
        assert serializer.data["sender"]["first_name"] == tenant_user.first_name
