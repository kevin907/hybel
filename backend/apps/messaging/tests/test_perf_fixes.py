"""
Tests for performance audit fixes.

Covers:
- Finding 1.1: MessagesSinceView duplicate participant query elimination
- Finding 1.2: mark_as_read atomic UPDATE (race condition fix)
- Finding 1.5: delegation broadcast pre-computed landlord IDs
- Finding 2.2: MessagesSinceView has_more flag
- Finding 4.1: Per-user group broadcasts (all events use user groups)
"""

from unittest.mock import patch

import pytest
from rest_framework import status

from apps.messaging.models import (
    ReadState,
)
from apps.messaging.services import (
    delegate_conversation,
    mark_as_read,
    remove_delegation,
    send_message,
)

from .conftest import (
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)

# ---------------------------------------------------------------------------
# Finding 1.1: MessagesSinceView — no duplicate participant query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessagesSinceViewOptimized:
    """MessagesSinceView should reuse the participant fetched for access
    control, not query it again via get_visible_messages()."""

    def test_gap_fill_returns_messages_after_since_id(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        msg1 = MessageFactory(conversation=conv, sender=landlord_user, content="First")
        msg2 = MessageFactory(conversation=conv, sender=landlord_user, content="Second")
        msg3 = MessageFactory(conversation=conv, sender=landlord_user, content="Third")

        response = tenant_client.get(
            f"/api/conversations/{conv.id}/messages/since/",
            {"since_id": str(msg1.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [r["id"] for r in response.data["results"]]
        assert str(msg2.id) in ids
        assert str(msg3.id) in ids
        assert str(msg1.id) not in ids

    def test_gap_fill_excludes_internal_for_tenant(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        msg1 = MessageFactory(conversation=conv, sender=landlord_user, content="Public")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Secret")

        response = tenant_client.get(
            f"/api/conversations/{conv.id}/messages/since/",
            {"since_id": str(msg1.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        # Internal comment should be excluded for tenant
        assert all(not r["is_internal"] for r in response.data["results"])

    def test_gap_fill_includes_internal_for_landlord(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        msg1 = MessageFactory(conversation=conv, sender=landlord_user, content="Public")
        internal = InternalCommentFactory(
            conversation=conv, sender=landlord_user, content="Secret"
        )

        response = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/",
            {"since_id": str(msg1.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [r["id"] for r in response.data["results"]]
        assert str(internal.id) in ids

    def test_gap_fill_returns_has_more_flag(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        msg1 = MessageFactory(conversation=conv, sender=landlord_user, content="Anchor")

        response = tenant_client.get(
            f"/api/conversations/{conv.id}/messages/since/",
            {"since_id": str(msg1.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "has_more" in response.data
        assert response.data["has_more"] is False

    def test_gap_fill_requires_since_id(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = tenant_client.get(f"/api/conversations/{conv.id}/messages/since/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_gap_fill_rejects_invalid_since_id(
        self, tenant_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        response = tenant_client.get(
            f"/api/conversations/{conv.id}/messages/since/",
            {"since_id": "not-a-uuid"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_gap_fill_query_count(
        self, tenant_client, conversation_with_participants, landlord_user
    ):
        """The gap-fill endpoint should use a bounded number of queries,
        not duplicate the participant lookup."""
        conv, _, _ = conversation_with_participants
        msg1 = MessageFactory(conversation=conv, sender=landlord_user, content="Anchor")
        for i in range(5):
            MessageFactory(conversation=conv, sender=landlord_user, content=f"Msg {i}")

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            response = tenant_client.get(
                f"/api/conversations/{conv.id}/messages/since/",
                {"since_id": str(msg1.id)},
            )
        assert response.status_code == status.HTTP_200_OK
        # Should be bounded: session + user + conversation + participant +
        # messages + attachments prefetch ≈ 6-8, NOT 2x participant lookups
        assert len(ctx.captured_queries) <= 10


# ---------------------------------------------------------------------------
# Finding 1.2: mark_as_read — atomic UPDATE, no read-modify-write
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMarkAsReadAtomic:
    """mark_as_read() should use an atomic UPDATE to set unread_count=0,
    not a read-modify-write pattern that can race with send_message."""

    def test_mark_as_read_sets_unread_to_zero(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=5)
        msg = MessageFactory(conversation=conv, sender=landlord_user, content="Read me")

        rs = mark_as_read(tenant_user, conv, msg.id)
        assert rs.unread_count == 0
        assert rs.last_read_message_id == msg.id

    def test_mark_as_read_then_new_message_increments(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        """After marking as read, a new message should increment from 0 to 1."""
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=3)
        ReadStateFactory(conversation=conv, user=landlord_user, unread_count=0)
        msg1 = MessageFactory(conversation=conv, sender=landlord_user, content="Msg 1")

        mark_as_read(tenant_user, conv, msg1.id)

        rs = ReadState.objects.get(conversation=conv, user=tenant_user)
        assert rs.unread_count == 0

        # New message increments via F-expression
        send_message(landlord_user, conv, "Msg 2")

        rs.refresh_from_db()
        assert rs.unread_count == 1

    def test_mark_as_read_uses_queryset_update(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        """Verify that mark_as_read goes through ReadState.objects.filter().update()
        by checking the SQL queries (no full model save)."""
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=5)
        msg = MessageFactory(conversation=conv, sender=landlord_user, content="Read me")

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            mark_as_read(tenant_user, conv, msg.id)

        update_queries = [
            q
            for q in ctx.captured_queries
            if q["sql"].startswith("UPDATE") and "readstate" in q["sql"].lower()
        ]
        # Should have exactly 1 UPDATE on readstate (the atomic update)
        assert len(update_queries) == 1


# ---------------------------------------------------------------------------
# Finding 1.5: delegation broadcast pre-computed landlord IDs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDelegationBroadcastOptimized:
    """delegate_conversation and remove_delegation should pre-compute
    landlord user IDs and pass them to the broadcast function."""

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.events.broadcast_delegation_change")
    def test_delegate_passes_landlord_ids(
        self,
        mock_broadcast,
        _mock_on_commit,
        conversation_with_participants,
        landlord_user,
        property_manager_user,
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )

        delegate_conversation(conv, property_manager_user, landlord_user, note="Test")

        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args
        # The landlord_user_ids kwarg should be passed
        assert "landlord_user_ids" in call_kwargs.kwargs
        landlord_ids = call_kwargs.kwargs["landlord_user_ids"]
        assert landlord_user.id in landlord_ids

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.events.broadcast_delegation_change")
    def test_remove_delegation_passes_landlord_ids(
        self, mock_broadcast, _mock_on_commit, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants

        # Create a delegation first
        delegate_conversation(conv, landlord_user, landlord_user, note="Setup")
        mock_broadcast.reset_mock()

        remove_delegation(conv, landlord_user)

        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args
        assert "landlord_user_ids" in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# Finding 4.1: Per-user group broadcasts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPerUserGroupBroadcasts:
    """All broadcast functions should send to user_{id} groups,
    not conversation_{id} groups."""

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.events._send_to_group")
    def test_regular_message_broadcasts_to_user_groups(
        self,
        mock_send,
        _mock_on_commit,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=0)
        ReadStateFactory(conversation=conv, user=landlord_user, unread_count=0)

        send_message(tenant_user, conv, "Hello landlord")

        # Should send to user_{landlord_user.id}, NOT conversation_{conv.id}
        groups_called = [call.args[0] for call in mock_send.call_args_list]
        assert f"user_{landlord_user.id}" in groups_called
        assert f"conversation_{conv.id}" not in groups_called
        # Sender should NOT receive their own message
        assert f"user_{tenant_user.id}" not in groups_called

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.events._send_to_group")
    def test_internal_message_only_broadcasts_to_landlord_side(
        self,
        mock_send,
        _mock_on_commit,
        multi_participant_conversation,
        landlord_user,
        tenant_user,
        property_manager_user,
    ):
        conv, participants = multi_participant_conversation
        for _user_key, p in participants.items():
            ReadStateFactory(conversation=conv, user=p.user, unread_count=0)

        send_message(
            landlord_user, conv, "Internal note", message_type="internal_comment", is_internal=True
        )

        groups_called = [call.args[0] for call in mock_send.call_args_list]
        # Tenant should NOT receive internal messages
        assert f"user_{tenant_user.id}" not in groups_called
        # Sender should NOT receive their own message
        assert f"user_{landlord_user.id}" not in groups_called
        # Property manager (landlord_side) SHOULD receive
        assert f"user_{property_manager_user.id}" in groups_called

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.events._send_to_group")
    def test_participant_change_broadcasts_to_user_groups(
        self,
        mock_send,
        _mock_on_commit,
        conversation_with_participants,
        landlord_user,
        tenant_user,
    ):
        from apps.messaging.services import add_participant

        conv, _, _ = conversation_with_participants
        new_user = UserFactory()

        add_participant(conv, new_user, "contractor", "landlord_side", landlord_user)

        groups_called = [call.args[0] for call in mock_send.call_args_list]
        # Should use user groups, not conversation group
        assert len(groups_called) > 0
        assert all(g.startswith("user_") for g in groups_called)
        assert not any(g.startswith("conversation_") for g in groups_called)

    @patch("apps.messaging.events._send_to_group")
    def test_typing_broadcasts_to_user_groups_excluding_sender(
        self, mock_send, conversation_with_participants, tenant_user, landlord_user
    ):
        from apps.messaging.events import broadcast_typing

        conv, _, _ = conversation_with_participants

        broadcast_typing(conv, tenant_user, started=True)

        groups_called = [call.args[0] for call in mock_send.call_args_list]
        # Should send to landlord via user group, not conversation group
        assert f"user_{landlord_user.id}" in groups_called
        # Sender excluded
        assert f"user_{tenant_user.id}" not in groups_called
        assert not any(g.startswith("conversation_") for g in groups_called)


# ---------------------------------------------------------------------------
# Admin list_select_related
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminSelectRelated:
    """Admin classes should have list_select_related to avoid N+1 queries."""

    def test_message_admin_has_select_related(self):
        from apps.messaging.admin import MessageAdmin

        assert hasattr(MessageAdmin, "list_select_related")
        assert "conversation" in MessageAdmin.list_select_related
        assert "sender" in MessageAdmin.list_select_related

    def test_participant_admin_has_select_related(self):
        from apps.messaging.admin import ConversationParticipantAdmin

        assert hasattr(ConversationParticipantAdmin, "list_select_related")
        assert "conversation" in ConversationParticipantAdmin.list_select_related
        assert "user" in ConversationParticipantAdmin.list_select_related

    def test_readstate_admin_has_select_related(self):
        from apps.messaging.admin import ReadStateAdmin

        assert hasattr(ReadStateAdmin, "list_select_related")
        assert "conversation" in ReadStateAdmin.list_select_related
        assert "user" in ReadStateAdmin.list_select_related

    def test_delegation_admin_has_select_related(self):
        from apps.messaging.admin import DelegationAdmin

        assert hasattr(DelegationAdmin, "list_select_related")
        assert "conversation" in DelegationAdmin.list_select_related
        assert "assigned_to" in DelegationAdmin.list_select_related
        assert "assigned_by" in DelegationAdmin.list_select_related
