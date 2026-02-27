import pytest

from apps.messaging.models import (
    ConversationParticipant,
    Delegation,
    Message,
    ReadState,
)
from apps.messaging.services import (
    add_participant,
    create_conversation,
    delegate_conversation,
    mark_as_read,
    remove_delegation,
    remove_participant,
    search_messages,
    send_message,
)

from .conftest import (
    AttachmentFactory,
    InternalCommentFactory,
    MessageFactory,
    ReadStateFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestCreateConversation:
    def test_initializes_read_states(self, tenant_user, landlord_user):
        conv = create_conversation(
            creator=tenant_user,
            participant_data=[
                {"user_id": tenant_user.id, "role": "tenant", "side": "tenant_side"},
                {
                    "user_id": landlord_user.id,
                    "role": "landlord",
                    "side": "landlord_side",
                },
            ],
            subject="Test",
        )
        assert ReadState.objects.filter(conversation=conv).count() == 2

    def test_creates_participants(self, tenant_user, landlord_user):
        conv = create_conversation(
            creator=tenant_user,
            participant_data=[
                {"user_id": tenant_user.id, "role": "tenant", "side": "tenant_side"},
                {
                    "user_id": landlord_user.id,
                    "role": "landlord",
                    "side": "landlord_side",
                },
            ],
        )
        assert ConversationParticipant.objects.filter(conversation=conv).count() == 2


@pytest.mark.django_db
class TestSendMessage:
    def test_increments_unread_for_others(self, conversation_with_participants, tenant_user):
        conv, _, landlord_p = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user)
        ReadStateFactory(conversation=conv, user=landlord_p.user)

        send_message(sender=tenant_user, conversation=conv, content="Hei")

        rs = ReadState.objects.get(conversation=conv, user=landlord_p.user)
        assert rs.unread_count == 1

    def test_does_not_increment_for_sender(self, conversation_with_participants, tenant_user):
        conv, _, landlord_p = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user)
        ReadStateFactory(conversation=conv, user=landlord_p.user)

        send_message(sender=tenant_user, conversation=conv, content="Hei")

        rs = ReadState.objects.get(conversation=conv, user=tenant_user)
        assert rs.unread_count == 0

    def test_internal_only_increments_landlord_side(self, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        for p in participants.values():
            ReadStateFactory(conversation=conv, user=p.user)

        send_message(
            sender=participants["landlord"].user,
            conversation=conv,
            content="Intern notat",
            message_type="internal_comment",
            is_internal=True,
        )

        tenant_rs = ReadState.objects.get(conversation=conv, user=participants["tenant"].user)
        assert tenant_rs.unread_count == 0

        manager_rs = ReadState.objects.get(conversation=conv, user=participants["manager"].user)
        assert manager_rs.unread_count == 1


@pytest.mark.django_db
class TestAddParticipant:
    def test_creates_system_message(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()
        add_participant(
            conversation=conv,
            user=new_user,
            role="contractor",
            side="landlord_side",
            added_by=landlord_user,
        )
        system_msgs = Message.objects.filter(conversation=conv, message_type="system_event")
        assert system_msgs.count() == 1
        assert new_user.first_name in system_msgs.first().content


@pytest.mark.django_db
class TestRemoveParticipant:
    def test_soft_deletes(self, conversation_with_participants, tenant_user, landlord_user):
        conv, _, _ = conversation_with_participants
        remove_participant(conv, tenant_user, removed_by=landlord_user)

        p = ConversationParticipant.objects.get(conversation=conv, user=tenant_user)
        assert p.is_active is False
        assert p.left_at is not None


@pytest.mark.django_db
class TestDelegateConversation:
    def test_deactivates_previous(
        self, conversation_with_participants, landlord_user, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        delegate_conversation(conv, property_manager_user, landlord_user)

        new_user = UserFactory()
        delegate_conversation(conv, new_user, landlord_user)

        assert Delegation.objects.filter(conversation=conv, is_active=True).count() == 1
        active = Delegation.objects.get(conversation=conv, is_active=True)
        assert active.assigned_to == new_user


@pytest.mark.django_db
class TestMarkAsRead:
    def test_resets_unread_count(self, conversation_with_participants, tenant_user, landlord_user):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=landlord_user)
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=5)

        rs = mark_as_read(tenant_user, conv, msg.id)
        assert rs.unread_count == 0
        assert rs.last_read_message == msg


@pytest.mark.django_db
class TestRemoveDelegation:
    def test_deactivates_and_creates_system_message(
        self, conversation_with_participants, landlord_user, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        delegate_conversation(conv, property_manager_user, landlord_user)

        remove_delegation(conv, landlord_user)

        assert not Delegation.objects.filter(conversation=conv, is_active=True).exists()
        system_msgs = Message.objects.filter(conversation=conv, message_type="system_event")
        assert system_msgs.filter(content__contains="Delegering ble fjernet").exists()


@pytest.mark.django_db
class TestSearchMessages:
    def test_search_messages_basic(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Det er en vannlekkasje på badet.",
        )
        results = search_messages(tenant_user, query="vannlekkasje")
        assert results.count() >= 1

    def test_search_messages_respects_visibility(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=landlord_user,
            content="Vi sender en rørlegger i morgen.",
        )
        InternalCommentFactory(
            conversation=conv,
            sender=landlord_user,
            content="Rørlegger koster 5000kr.",
        )
        results = search_messages(tenant_user, query="rørlegger")
        assert results.count() == 1
        assert not results.filter(is_internal=True).exists()

    def test_search_messages_with_filters(
        self, conversation_with_participants, tenant_user, landlord_user, sample_property
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Heisen er ødelagt igjen.",
        )
        results = search_messages(
            tenant_user,
            filters={"property": sample_property.id, "status": "open"},
        )
        assert results.count() >= 1

    def test_search_with_conversation_type_filter(
        self, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Type test")
        results = search_messages(
            tenant_user,
            filters={"conversation_type": "general"},
        )
        assert results.count() >= 1

    def test_search_with_unread_only_filter(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Ulest melding")
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=2)

        results = search_messages(tenant_user, filters={"unread_only": True})
        assert results.count() >= 1

    def test_search_with_has_attachment_filter(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user, content="Med vedlegg")
        AttachmentFactory(message=msg)

        results = search_messages(tenant_user, filters={"has_attachment": True})
        assert results.count() >= 1

    def test_search_with_no_results(self, conversation_with_participants, tenant_user):
        results = search_messages(tenant_user, query="finnesikke123xyz")
        assert results.count() == 0


@pytest.mark.django_db
class TestRemoveParticipantExtended:
    def test_creates_system_message(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        remove_participant(conv, tenant_user, removed_by=landlord_user)

        system_msgs = Message.objects.filter(conversation=conv, message_type="system_event")
        assert system_msgs.count() == 1
        assert tenant_user.first_name in system_msgs.first().content


@pytest.mark.django_db
class TestAddParticipantExtended:
    def test_creates_read_state(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()
        add_participant(
            conversation=conv,
            user=new_user,
            role="contractor",
            side="landlord_side",
            added_by=landlord_user,
        )
        assert ReadState.objects.filter(conversation=conv, user=new_user).exists()
