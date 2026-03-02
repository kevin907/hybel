"""
WebSocket event contract tests: verify broadcast payloads match
frontend/src/types/messaging.ts WSEvent union type.

Every event field is checked against the TypeScript interface to catch
backend-frontend misalignment.
"""

from unittest.mock import patch

import pytest

from .conftest import (
    ConversationFactory,
    DelegationFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    UserFactory,
)

# ──────────────────────────────────────────────
# Contract: WSMessageNew
# ──────────────────────────────────────────────

WS_MESSAGE_NEW_REQUIRED = {
    "type",
    "message_id",
    "conversation_id",
    "sender_id",
    "sender_first_name",
    "sender_last_name",
    "sender_email",
    "content",
    "message_type",
    "is_internal",
}


@pytest.mark.django_db
class TestWSMessageNewContract:
    """broadcast_new_message payload → WSMessageNew interface."""

    @patch("apps.messaging.events._send_to_group")
    def test_public_message_payload_shape(self, mock_send):
        from apps.messaging.events import broadcast_new_message

        conv = ConversationFactory()
        user = UserFactory()
        ParticipantFactory(conversation=conv, user=user, side="landlord_side")
        msg = MessageFactory(conversation=conv, sender=user)

        broadcast_new_message(msg)

        mock_send.assert_called()
        payload = mock_send.call_args[0][1]
        # Backend adds "version" which frontend ignores — acceptable
        payload_keys = set(payload.keys()) - {"version"}
        assert payload_keys == WS_MESSAGE_NEW_REQUIRED
        assert payload["type"] == "message.new"
        assert isinstance(payload["message_id"], str)
        assert isinstance(payload["is_internal"], bool)
        assert payload["is_internal"] is False

    @patch("apps.messaging.events._send_to_group")
    def test_public_message_sent_to_conversation_group(self, mock_send):
        from apps.messaging.events import broadcast_new_message

        conv = ConversationFactory()
        user = UserFactory()
        ParticipantFactory(conversation=conv, user=user, side="landlord_side")
        msg = MessageFactory(conversation=conv, sender=user)

        broadcast_new_message(msg)

        group_name = mock_send.call_args[0][0]
        assert group_name == f"conversation_{conv.id}"

    @patch("apps.messaging.events._send_to_group")
    def test_internal_message_sent_to_user_groups(self, mock_send):
        """Internal messages go to user_{uid} groups, not conversation group."""
        from apps.messaging.events import broadcast_new_message

        conv = ConversationFactory()
        landlord1 = UserFactory()
        landlord2 = UserFactory()
        ParticipantFactory(conversation=conv, user=landlord1, side="landlord_side")
        ParticipantFactory(conversation=conv, user=landlord2, side="landlord_side")
        msg = InternalCommentFactory(conversation=conv, sender=landlord1)

        broadcast_new_message(msg)

        for c in mock_send.call_args_list:
            group_name = c[0][0]
            assert group_name.startswith("user_"), (
                f"Internal message should go to user groups, got: {group_name}"
            )

    @patch("apps.messaging.events._send_to_group")
    def test_internal_message_not_sent_to_sender(self, mock_send):
        """Sender should not receive their own internal message."""
        from apps.messaging.events import broadcast_new_message

        conv = ConversationFactory()
        sender = UserFactory()
        other = UserFactory()
        ParticipantFactory(conversation=conv, user=sender, side="landlord_side")
        ParticipantFactory(conversation=conv, user=other, side="landlord_side")
        msg = InternalCommentFactory(conversation=conv, sender=sender)

        broadcast_new_message(msg)

        sent_groups = [c[0][0] for c in mock_send.call_args_list]
        assert f"user_{sender.id}" not in sent_groups
        assert f"user_{other.id}" in sent_groups


# ──────────────────────────────────────────────
# Contract: WSReadUpdated
# ──────────────────────────────────────────────

WS_READ_UPDATED_REQUIRED = {"type", "conversation_id", "unread_count"}


@pytest.mark.django_db
class TestWSReadUpdatedContract:
    @patch("apps.messaging.events._send_to_group")
    def test_read_updated_payload_shape(self, mock_send):
        from apps.messaging.events import broadcast_read_update

        conv = ConversationFactory()
        user = UserFactory()

        broadcast_read_update(user, conv, 0)

        payload = mock_send.call_args[0][1]
        payload_keys = set(payload.keys()) - {"version"}
        assert payload_keys == WS_READ_UPDATED_REQUIRED
        assert payload["type"] == "read.updated"
        assert isinstance(payload["unread_count"], int)
        assert payload["unread_count"] == 0

    @patch("apps.messaging.events._send_to_group")
    def test_read_updated_sent_to_user_group(self, mock_send):
        from apps.messaging.events import broadcast_read_update

        conv = ConversationFactory()
        user = UserFactory()

        broadcast_read_update(user, conv, 3)

        group_name = mock_send.call_args[0][0]
        assert group_name == f"user_{user.id}"


# ──────────────────────────────────────────────
# Contract: WSParticipantChange
# ──────────────────────────────────────────────

WS_PARTICIPANT_CHANGE_REQUIRED = {"type", "conversation_id", "user_id", "user_name"}


@pytest.mark.django_db
class TestWSParticipantChangeContract:
    @patch("apps.messaging.events._send_to_group")
    def test_participant_added_payload(self, mock_send):
        from apps.messaging.events import broadcast_participant_change

        conv = ConversationFactory()
        user = UserFactory(first_name="Kari", last_name="Hansen")

        broadcast_participant_change(conv, user, "added")

        payload = mock_send.call_args[0][1]
        payload_keys = set(payload.keys()) - {"version"}
        assert payload_keys == WS_PARTICIPANT_CHANGE_REQUIRED
        assert payload["type"] == "participant.added"
        assert payload["user_name"] == "Kari Hansen"

    @patch("apps.messaging.events._send_to_group")
    def test_participant_removed_payload(self, mock_send):
        from apps.messaging.events import broadcast_participant_change

        conv = ConversationFactory()
        user = UserFactory(first_name="Per", last_name="Olsen")

        broadcast_participant_change(conv, user, "removed")

        payload = mock_send.call_args[0][1]
        assert payload["type"] == "participant.removed"
        assert payload["user_id"] == str(user.id)

    @patch("apps.messaging.events._send_to_group")
    def test_participant_change_sent_to_conversation_group(self, mock_send):
        from apps.messaging.events import broadcast_participant_change

        conv = ConversationFactory()
        user = UserFactory()

        broadcast_participant_change(conv, user, "added")

        group_name = mock_send.call_args[0][0]
        assert group_name == f"conversation_{conv.id}"


# ──────────────────────────────────────────────
# Contract: WSDelegationChange
# ──────────────────────────────────────────────

WS_DELEGATION_ASSIGNED_REQUIRED = {
    "type",
    "conversation_id",
    "assigned_to_id",
    "assigned_by_id",
}

WS_DELEGATION_REMOVED_REQUIRED = {"type", "conversation_id"}


@pytest.mark.django_db
class TestWSDelegationChangeContract:
    @patch("apps.messaging.events._send_to_group")
    def test_delegation_assigned_payload(self, mock_send):
        from apps.messaging.events import broadcast_delegation_change

        conv = ConversationFactory()
        landlord = UserFactory()
        ParticipantFactory(conversation=conv, user=landlord, side="landlord_side")
        deleg = DelegationFactory(conversation=conv, assigned_to=landlord, assigned_by=landlord)

        broadcast_delegation_change(conv, deleg, "assigned")

        # May send to multiple user groups — check the payload shape of any call
        for c in mock_send.call_args_list:
            payload = c[0][1]
            payload_keys = set(payload.keys()) - {"version"}
            assert payload_keys == WS_DELEGATION_ASSIGNED_REQUIRED
            assert payload["type"] == "delegation.assigned"
            assert isinstance(payload["assigned_to_id"], str)

    @patch("apps.messaging.events._send_to_group")
    def test_delegation_removed_payload(self, mock_send):
        from apps.messaging.events import broadcast_delegation_change

        conv = ConversationFactory()
        landlord = UserFactory()
        ParticipantFactory(conversation=conv, user=landlord, side="landlord_side")

        broadcast_delegation_change(conv, None, "removed")

        for c in mock_send.call_args_list:
            payload = c[0][1]
            payload_keys = set(payload.keys()) - {"version"}
            assert payload_keys == WS_DELEGATION_REMOVED_REQUIRED
            assert payload["type"] == "delegation.removed"
            # Removed event should NOT have assigned_to_id
            assert "assigned_to_id" not in payload


# ──────────────────────────────────────────────
# Contract: WSTyping
# ──────────────────────────────────────────────

WS_TYPING_REQUIRED = {"type", "conversation_id", "user_id", "user_name"}


@pytest.mark.django_db
class TestWSTypingContract:
    @patch("apps.messaging.events._send_to_group")
    def test_typing_started_payload(self, mock_send):
        from apps.messaging.events import broadcast_typing

        conv = ConversationFactory()
        user = UserFactory(first_name="Ola", last_name="Nordmann")

        broadcast_typing(conv, user, started=True)

        payload = mock_send.call_args[0][1]
        payload_keys = set(payload.keys()) - {"version"}
        assert payload_keys == WS_TYPING_REQUIRED
        assert payload["type"] == "typing.started"
        assert payload["user_name"] == "Ola Nordmann"

    @patch("apps.messaging.events._send_to_group")
    def test_typing_stopped_payload(self, mock_send):
        from apps.messaging.events import broadcast_typing

        conv = ConversationFactory()
        user = UserFactory()

        broadcast_typing(conv, user, started=False)

        payload = mock_send.call_args[0][1]
        assert payload["type"] == "typing.stopped"

    @patch("apps.messaging.events._send_to_group")
    def test_typing_sent_to_conversation_group(self, mock_send):
        from apps.messaging.events import broadcast_typing

        conv = ConversationFactory()
        user = UserFactory()

        broadcast_typing(conv, user, started=True)

        group_name = mock_send.call_args[0][0]
        assert group_name == f"conversation_{conv.id}"
