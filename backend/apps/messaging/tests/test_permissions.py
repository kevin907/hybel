import pytest
from rest_framework.exceptions import PermissionDenied

from apps.messaging.permissions import (
    can_see_message,
    get_user_conversations,
    get_user_side,
    get_visible_messages,
)

from .conftest import (
    ConversationFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestGetUserSide:
    def test_tenant_returns_tenant_side(self, conversation_with_participants):
        conv, tenant_p, _ = conversation_with_participants
        assert get_user_side(tenant_p.user, conv) == "tenant_side"

    def test_landlord_returns_landlord_side(self, conversation_with_participants):
        conv, _, landlord_p = conversation_with_participants
        assert get_user_side(landlord_p.user, conv) == "landlord_side"

    def test_contractor_on_landlord_side(self, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        assert get_user_side(participants["contractor"].user, conv) == "landlord_side"

    def test_inactive_participant_raises(self, conversation_with_participants, tenant_user):
        conv, tenant_p, _ = conversation_with_participants
        tenant_p.is_active = False
        tenant_p.save()
        with pytest.raises(PermissionDenied):
            get_user_side(tenant_user, conv)


@pytest.mark.django_db
class TestCanSeeMessage:
    def test_tenant_can_see_regular_message(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=landlord_user, is_internal=False)
        assert can_see_message(tenant_user, msg) is True

    def test_tenant_cannot_see_internal_comment(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        comment = InternalCommentFactory(conversation=conv, sender=landlord_user)
        assert can_see_message(tenant_user, comment) is False

    def test_landlord_can_see_internal_comment(
        self, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        comment = InternalCommentFactory(conversation=conv, sender=landlord_user)
        assert can_see_message(landlord_user, comment) is True

    def test_contractor_landlord_side_can_see_internal(self, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        comment = InternalCommentFactory(
            conversation=conv,
            sender=participants["landlord"].user,
        )
        assert can_see_message(participants["contractor"].user, comment) is True

    def test_system_event_visible_to_all(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        event = MessageFactory(
            conversation=conv,
            sender=landlord_user,
            message_type="system_event",
            is_internal=False,
        )
        assert can_see_message(tenant_user, event) is True
        assert can_see_message(landlord_user, event) is True


@pytest.mark.django_db
class TestGetVisibleMessages:
    def test_tenant_sees_only_regular_messages(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        for _ in range(3):
            MessageFactory(conversation=conv, sender=landlord_user)
        for _ in range(2):
            InternalCommentFactory(conversation=conv, sender=landlord_user)

        visible = get_visible_messages(tenant_user, conv)
        assert visible.count() == 3
        assert not visible.filter(is_internal=True).exists()

    def test_landlord_sees_all_messages(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        for _ in range(3):
            MessageFactory(conversation=conv, sender=landlord_user)
        for _ in range(2):
            InternalCommentFactory(conversation=conv, sender=landlord_user)

        visible = get_visible_messages(landlord_user, conv)
        assert visible.count() == 5

    def test_newly_added_tenant_cannot_see_internal(self, conversation_with_participants):
        conv, _, landlord_p = conversation_with_participants
        InternalCommentFactory(conversation=conv, sender=landlord_p.user)

        new_tenant = UserFactory()
        ParticipantFactory(
            conversation=conv,
            user=new_tenant,
            role="tenant",
            side="tenant_side",
        )

        visible = get_visible_messages(new_tenant, conv)
        assert not visible.filter(is_internal=True).exists()


@pytest.mark.django_db
class TestGetUserConversations:
    def test_user_only_sees_own_conversations(self, conversation_with_participants, tenant_user):
        other_conv = ConversationFactory()
        other_user = UserFactory()
        ParticipantFactory(
            conversation=other_conv,
            user=other_user,
            role="tenant",
            side="tenant_side",
        )

        convs = get_user_conversations(tenant_user)
        assert convs.count() == 1

    def test_inactive_participant_excluded(self, conversation_with_participants, tenant_user):
        _conv, tenant_p, _ = conversation_with_participants
        tenant_p.is_active = False
        tenant_p.save()

        convs = get_user_conversations(tenant_user)
        assert convs.count() == 0
