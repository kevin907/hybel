from unittest.mock import MagicMock, patch

import pytest

from apps.messaging.events import (
    _get_landlord_side_user_ids,
    _send_to_group,
    broadcast_delegation_change,
    broadcast_new_message,
    broadcast_participant_change,
    broadcast_read_update,
    broadcast_typing,
)

from .conftest import (
    DelegationFactory,
    InternalCommentFactory,
    MessageFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestSendToGroup:
    @patch("apps.messaging.events.get_channel_layer")
    def test_sends_event_to_group(self, mock_get_layer):
        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer

        _send_to_group("test_group", {"type": "test.event"})

        mock_layer.group_send.assert_called_once()

    @patch("apps.messaging.events.get_channel_layer")
    def test_handles_none_channel_layer(self, mock_get_layer):
        mock_get_layer.return_value = None
        # Should not raise
        _send_to_group("test_group", {"type": "test.event"})

    @patch("apps.messaging.events.get_channel_layer")
    def test_handles_exception_gracefully(self, mock_get_layer):
        mock_layer = MagicMock()
        mock_layer.group_send.side_effect = Exception("Channel error")
        mock_get_layer.return_value = mock_layer

        # Should not raise
        _send_to_group("test_group", {"type": "test.event"})


@pytest.mark.django_db
class TestGetLandlordSideUserIds:
    def test_returns_landlord_side_users(self, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        ids = _get_landlord_side_user_ids(conv)
        assert str(participants["landlord"].user.id) in ids
        assert str(participants["manager"].user.id) in ids
        assert str(participants["contractor"].user.id) in ids
        assert str(participants["tenant"].user.id) not in ids

    def test_excludes_inactive(self, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        participants["contractor"].is_active = False
        participants["contractor"].save()

        ids = _get_landlord_side_user_ids(conv)
        assert str(participants["contractor"].user.id) not in ids


@pytest.mark.django_db
class TestBroadcastNewMessage:
    @patch("apps.messaging.events._send_to_group")
    def test_regular_message_sends_to_conversation_group(
        self, mock_send, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        broadcast_new_message(msg)

        mock_send.assert_called_once()
        group_name = mock_send.call_args[0][0]
        assert group_name == f"conversation_{conv.id}"

    @patch("apps.messaging.events._send_to_group")
    def test_internal_message_sends_to_user_groups(
        self, mock_send, multi_participant_conversation
    ):
        conv, participants = multi_participant_conversation
        msg = InternalCommentFactory(conversation=conv, sender=participants["landlord"].user)

        broadcast_new_message(msg)

        # Should send to landlord-side users except the sender
        group_names = [call[0][0] for call in mock_send.call_args_list]
        assert f"user_{participants['landlord'].user.id}" not in group_names
        assert f"user_{participants['manager'].user.id}" in group_names
        assert f"user_{participants['contractor'].user.id}" in group_names


@pytest.mark.django_db
class TestBroadcastReadUpdate:
    @patch("apps.messaging.events._send_to_group")
    def test_sends_to_user_group(self, mock_send, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants

        broadcast_read_update(tenant_user, conv, 0)

        mock_send.assert_called_once()
        group_name = mock_send.call_args[0][0]
        assert group_name == f"user_{tenant_user.id}"
        event = mock_send.call_args[0][1]
        assert event["unread_count"] == 0


@pytest.mark.django_db
class TestBroadcastParticipantChange:
    @patch("apps.messaging.events._send_to_group")
    def test_sends_added_event(self, mock_send, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()

        broadcast_participant_change(conv, new_user, "added")

        event = mock_send.call_args[0][1]
        assert event["type"] == "participant.added"
        assert event["user_id"] == str(new_user.id)

    @patch("apps.messaging.events._send_to_group")
    def test_sends_removed_event(self, mock_send, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants

        broadcast_participant_change(conv, tenant_user, "removed")

        event = mock_send.call_args[0][1]
        assert event["type"] == "participant.removed"


@pytest.mark.django_db
class TestBroadcastDelegationChange:
    @patch("apps.messaging.events._send_to_group")
    def test_sends_assigned_with_delegation(
        self, mock_send, conversation_with_participants, landlord_user, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        delegation = DelegationFactory(
            conversation=conv, assigned_to=property_manager_user, assigned_by=landlord_user
        )

        broadcast_delegation_change(conv, delegation, "assigned")

        event = mock_send.call_args[0][1]
        assert event["type"] == "delegation.assigned"
        assert "assigned_to_id" in event

    @patch("apps.messaging.events._send_to_group")
    def test_sends_removed_without_delegation(self, mock_send, conversation_with_participants):
        conv, _, _ = conversation_with_participants

        broadcast_delegation_change(conv, None, "removed")

        event = mock_send.call_args[0][1]
        assert event["type"] == "delegation.removed"
        assert "assigned_to_id" not in event


@pytest.mark.django_db
class TestBroadcastTyping:
    @patch("apps.messaging.events._send_to_group")
    def test_sends_started(self, mock_send, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants

        broadcast_typing(conv, tenant_user, started=True)

        event = mock_send.call_args[0][1]
        assert event["type"] == "typing.started"

    @patch("apps.messaging.events._send_to_group")
    def test_sends_stopped(self, mock_send, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants

        broadcast_typing(conv, tenant_user, started=False)

        event = mock_send.call_args[0][1]
        assert event["type"] == "typing.stopped"
