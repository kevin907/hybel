import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.messaging.models import Conversation, ConversationParticipant

from .conftest import (
    AttachmentFactory,
    ConversationFactory,
    DelegationFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
)


@pytest.mark.django_db
class TestConversation:
    def test_create_conversation(self, sample_property):
        conv = ConversationFactory(property=sample_property, subject="Nøkkelbytte")
        assert conv.status == "open"
        assert conv.conversation_type == "general"
        assert str(conv.property) == "Storgata 15, Oslo"

    def test_conversation_ordering(self):
        old = ConversationFactory()
        new = ConversationFactory()
        convs = list(Conversation.objects.all())
        assert convs[0] == new
        assert convs[1] == old


@pytest.mark.django_db
class TestConversationParticipant:
    def test_unique_constraint(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        with pytest.raises(IntegrityError):
            ParticipantFactory(
                conversation=conv,
                user=tenant_user,
                role="tenant",
                side="tenant_side",
            )

    def test_soft_remove_preserves_record(self, conversation_with_participants):
        conv, tenant_p, _ = conversation_with_participants
        tenant_p.is_active = False
        tenant_p.left_at = timezone.now()
        tenant_p.save()

        assert ConversationParticipant.objects.filter(
            conversation=conv, user=tenant_p.user
        ).exists()


@pytest.mark.django_db
class TestMessage:
    def test_internal_flag_synced_with_type(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        comment = InternalCommentFactory(conversation=conv, sender=landlord_user)
        assert comment.is_internal is True
        assert comment.message_type == "internal_comment"

    def test_messages_ordered_by_created_at(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        m1 = MessageFactory(conversation=conv, sender=landlord_user)
        m2 = MessageFactory(conversation=conv, sender=landlord_user)
        msgs = list(conv.messages.all())
        assert msgs == [m1, m2]


@pytest.mark.django_db
class TestReadState:
    def test_unread_count_starts_at_zero(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        rs = ReadStateFactory(conversation=conv, user=tenant_user)
        assert rs.unread_count == 0

    def test_unique_per_user_per_conversation(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user)
        with pytest.raises(IntegrityError):
            ReadStateFactory(conversation=conv, user=tenant_user)


@pytest.mark.django_db
class TestDelegation:
    def test_create_delegation(
        self, conversation_with_participants, landlord_user, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        d = DelegationFactory(
            conversation=conv,
            assigned_to=property_manager_user,
            assigned_by=landlord_user,
        )
        assert d.is_active is True
        assert d.assigned_to == property_manager_user


@pytest.mark.django_db
class TestAttachment:
    def test_create_attachment(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)
        att = AttachmentFactory(message=msg, filename="kvittering.pdf", file_size=2048)
        assert att.message == msg
        assert msg.attachments.count() == 1
