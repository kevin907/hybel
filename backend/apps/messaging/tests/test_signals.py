import pytest

from apps.messaging.models import Message, MessageType

from .conftest import ConversationFactory, UserFactory


@pytest.mark.django_db
class TestSyncInternalFlag:
    def test_internal_comment_sets_is_internal_true(self, db):
        user = UserFactory()
        conv = ConversationFactory()
        msg = Message.objects.create(
            conversation=conv,
            sender=user,
            content="Internal note",
            message_type=MessageType.INTERNAL_COMMENT,
        )
        assert msg.is_internal is True

    def test_regular_message_sets_is_internal_false(self, db):
        user = UserFactory()
        conv = ConversationFactory()
        msg = Message.objects.create(
            conversation=conv,
            sender=user,
            content="Hello",
            message_type=MessageType.MESSAGE,
        )
        assert msg.is_internal is False

    def test_system_event_sets_is_internal_false(self, db):
        user = UserFactory()
        conv = ConversationFactory()
        msg = Message.objects.create(
            conversation=conv,
            sender=user,
            content="User joined",
            message_type=MessageType.SYSTEM_EVENT,
        )
        assert msg.is_internal is False

    def test_updating_type_updates_is_internal(self, db):
        user = UserFactory()
        conv = ConversationFactory()
        msg = Message.objects.create(
            conversation=conv,
            sender=user,
            content="Was regular",
            message_type=MessageType.MESSAGE,
        )
        assert msg.is_internal is False

        msg.message_type = MessageType.INTERNAL_COMMENT
        msg.save()
        msg.refresh_from_db()
        assert msg.is_internal is True
