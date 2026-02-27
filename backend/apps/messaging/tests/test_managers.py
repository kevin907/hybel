import pytest

from apps.messaging.models import Message

from .conftest import (
    ConversationFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
)


@pytest.mark.django_db
class TestMessageVisibleTo:
    def test_tenant_sees_only_non_internal(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user)
        InternalCommentFactory(conversation=conv, sender=landlord_user)

        tenant_user = conv.participants.get(side="tenant_side").user
        visible = Message.objects.visible_to(tenant_user, conv)
        assert visible.count() == 1
        assert not visible.filter(is_internal=True).exists()

    def test_landlord_sees_all(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user)
        InternalCommentFactory(conversation=conv, sender=landlord_user)

        visible = Message.objects.visible_to(landlord_user, conv)
        assert visible.count() == 2

    def test_scopes_to_conversation(self, conversation_with_participants, landlord_user):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user)

        other_conv = ConversationFactory()
        ParticipantFactory(
            conversation=other_conv, user=landlord_user, role="landlord", side="landlord_side"
        )
        MessageFactory(conversation=other_conv, sender=landlord_user)

        visible = Message.objects.visible_to(landlord_user, conv)
        assert visible.count() == 1
        assert all(m.conversation_id == conv.id for m in visible)

    def test_without_conversation_scopes_across_all(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user)
        InternalCommentFactory(conversation=conv, sender=landlord_user)

        visible = Message.objects.filter(conversation_id__in=[conv.id]).visible_to(tenant_user)
        assert visible.count() == 1
        assert not visible.filter(is_internal=True).exists()

    def test_inactive_participant_returns_empty(self, conversation_with_participants, tenant_user):
        conv, tenant_p, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        tenant_p.is_active = False
        tenant_p.save()

        visible = Message.objects.visible_to(tenant_user, conv)
        assert visible.count() == 0

    def test_contractor_landlord_side_sees_internal(self, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        InternalCommentFactory(conversation=conv, sender=participants["landlord"].user)

        visible = Message.objects.visible_to(participants["contractor"].user, conv)
        assert visible.filter(is_internal=True).count() == 1
