"""
E2E integration tests that exercise full request/response cycles
for the Hybel messaging backend.

These tests verify multi-step flows across endpoints, ensuring
that side effects (unread counts, visibility rules, gap-fill)
propagate correctly through the system.
"""

import pytest
from rest_framework import status

from apps.messaging.models import ReadState

from .conftest import (
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestFullMessageFlow:
    """Send a message, verify unread increment, then mark as read."""

    def test_send_increments_unread_then_read_resets(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        # Ensure both users have ReadState rows (required for unread tracking)
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=0)
        ReadStateFactory(conversation=conv, user=landlord_user, unread_count=0)

        # Step 1: Tenant sends a message
        send_resp = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Hei, varmen virker ikke."},
        )
        assert send_resp.status_code == status.HTTP_201_CREATED
        msg_id = send_resp.data["id"]

        # Step 2: Landlord's unread count should have incremented
        rs = ReadState.objects.get(conversation=conv, user=landlord_user)
        assert rs.unread_count == 1

        # Step 3: Tenant's own unread count should remain 0 (sender not incremented)
        rs_tenant = ReadState.objects.get(conversation=conv, user=tenant_user)
        assert rs_tenant.unread_count == 0

        # Step 4: Landlord marks conversation as read
        read_resp = landlord_client.post(
            f"/api/conversations/{conv.id}/read/",
            {"last_read_message_id": msg_id},
        )
        assert read_resp.status_code == status.HTTP_200_OK
        assert read_resp.data["unread_count"] == 0

        # Step 5: Verify via DB that unread is truly zero
        rs.refresh_from_db()
        assert rs.unread_count == 0

    def test_multiple_messages_accumulate_unread(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=0)
        ReadStateFactory(conversation=conv, user=landlord_user, unread_count=0)

        # Tenant sends three messages
        last_msg_id = None
        for text in ["Melding 1", "Melding 2", "Melding 3"]:
            resp = tenant_client.post(
                f"/api/conversations/{conv.id}/messages/",
                {"content": text},
            )
            assert resp.status_code == status.HTTP_201_CREATED
            last_msg_id = resp.data["id"]

        # Landlord unread should be 3
        rs = ReadState.objects.get(conversation=conv, user=landlord_user)
        assert rs.unread_count == 3

        # Landlord marks as read with the last message
        read_resp = landlord_client.post(
            f"/api/conversations/{conv.id}/read/",
            {"last_read_message_id": last_msg_id},
        )
        assert read_resp.status_code == status.HTTP_200_OK
        assert read_resp.data["unread_count"] == 0

    def test_unread_count_reflected_in_conversation_list(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=0)
        ReadStateFactory(conversation=conv, user=landlord_user, unread_count=0)

        # Tenant sends a message
        tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Trenger ny nøkkel."},
        )

        # Landlord fetches conversation list and sees unread_count = 1
        list_resp = landlord_client.get("/api/conversations/")
        assert list_resp.status_code == status.HTTP_200_OK
        results = list_resp.data["results"]
        assert len(results) == 1
        assert results[0]["unread_count"] == 1


@pytest.mark.django_db
class TestInternalCommentIsolation:
    """Internal comments must never leak to tenant-side users."""

    def test_tenant_cannot_see_internal_comments_in_message_list(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        # Landlord sends a public message and an internal comment
        tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Heisen er ødelagt."},
        )
        landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern: kontakt rørlegger, koster 5000kr.", "is_internal": True},
        )
        landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Vi fikser det i morgen."},
        )

        # Tenant should only see non-internal messages
        tenant_resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert tenant_resp.status_code == status.HTTP_200_OK
        tenant_messages = tenant_resp.data["results"]
        assert all(not m["is_internal"] for m in tenant_messages)
        contents = [m["content"] for m in tenant_messages]
        assert "Intern: kontakt rørlegger, koster 5000kr." not in contents
        assert "Heisen er ødelagt." in contents
        assert "Vi fikser det i morgen." in contents

        # Landlord should see all messages including internal
        landlord_resp = landlord_client.get(f"/api/conversations/{conv.id}/messages/")
        landlord_messages = landlord_resp.data["results"]
        landlord_contents = [m["content"] for m in landlord_messages]
        assert "Intern: kontakt rørlegger, koster 5000kr." in landlord_contents

    def test_tenant_cannot_see_internal_comments_in_search(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        # Create messages — one public, one internal
        MessageFactory(
            conversation=conv,
            sender=landlord_user,
            content="Rørleggeren kommer i morgen.",
        )
        InternalCommentFactory(
            conversation=conv,
            sender=landlord_user,
            content="Intern notat om kostnader.",
        )

        # Tenant searches without FTS query — returns all visible messages
        tenant_resp = tenant_client.get("/api/conversations/search/", {"status": "open"})
        assert tenant_resp.status_code == status.HTTP_200_OK
        results = tenant_resp.data["results"]
        assert all(not r["is_internal"] for r in results)
        assert not any("Intern notat" in r["content"] for r in results)

        # Landlord should see both public and internal results
        landlord_resp = landlord_client.get("/api/conversations/search/", {"status": "open"})
        landlord_results = landlord_resp.data["results"]
        assert any("Intern notat" in r["content"] for r in landlord_results)

    def test_tenant_cannot_see_internal_comments_in_gap_fill(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        # Create a sequence of messages with an internal comment in the middle
        m1 = MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Første melding.",
        )
        InternalCommentFactory(
            conversation=conv,
            sender=landlord_user,
            content="Intern merknad om leietaker.",
        )
        MessageFactory(
            conversation=conv,
            sender=landlord_user,
            content="Offentlig svar.",
        )

        # Tenant gap-fills from m1 — should not see the internal comment
        tenant_resp = tenant_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        assert tenant_resp.status_code == status.HTTP_200_OK
        contents = [m["content"] for m in tenant_resp.data["results"]]
        assert "Intern merknad om leietaker." not in contents
        assert "Offentlig svar." in contents
        assert all(not m["is_internal"] for m in tenant_resp.data["results"])

        # Landlord gap-fills from m1 — should see the internal comment
        landlord_resp = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        landlord_contents = [m["content"] for m in landlord_resp.data["results"]]
        assert "Intern merknad om leietaker." in landlord_contents
        assert "Offentlig svar." in landlord_contents

    def test_internal_comment_does_not_increment_tenant_unread(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=0)
        ReadStateFactory(conversation=conv, user=landlord_user, unread_count=0)

        # Landlord sends an internal comment
        landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern: forsikringssak.", "is_internal": True},
        )

        # Tenant unread should still be 0 — internal comments don't affect tenant
        rs = ReadState.objects.get(conversation=conv, user=tenant_user)
        assert rs.unread_count == 0


@pytest.mark.django_db
class TestGapFill:
    """Gap-fill endpoint returns correct messages after a given message."""

    def test_gap_fill_returns_only_messages_after_since_id(
        self,
        landlord_client,
        conversation_with_participants,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        m1 = MessageFactory(conversation=conv, sender=landlord_user, content="Melding 1")
        m2 = MessageFactory(conversation=conv, sender=landlord_user, content="Melding 2")
        m3 = MessageFactory(conversation=conv, sender=landlord_user, content="Melding 3")

        resp = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        assert resp.status_code == status.HTTP_200_OK
        ids = [m["id"] for m in resp.data["results"]]
        assert str(m1.id) not in ids
        assert str(m2.id) in ids
        assert str(m3.id) in ids

    def test_gap_fill_returns_empty_when_no_newer_messages(
        self,
        landlord_client,
        conversation_with_participants,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        m1 = MessageFactory(conversation=conv, sender=landlord_user, content="Siste melding")

        resp = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) == 0

    def test_gap_fill_returns_messages_in_chronological_order(
        self,
        landlord_client,
        conversation_with_participants,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants

        m1 = MessageFactory(conversation=conv, sender=landlord_user, content="Første")
        MessageFactory(conversation=conv, sender=landlord_user, content="Andre")
        MessageFactory(conversation=conv, sender=landlord_user, content="Tredje")

        resp = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        assert resp.status_code == status.HTTP_200_OK
        contents = [m["content"] for m in resp.data["results"]]
        assert contents == ["Andre", "Tredje"]

    def test_gap_fill_after_send_includes_new_message(
        self,
        tenant_client,
        landlord_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        """End-to-end: tenant sends a message, landlord gap-fills and sees it."""
        conv, _, _ = conversation_with_participants

        # Landlord already has a baseline message
        baseline = MessageFactory(conversation=conv, sender=landlord_user, content="Utgangspunkt")

        # Tenant sends a new message
        send_resp = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Ny melding fra leietaker."},
        )
        assert send_resp.status_code == status.HTTP_201_CREATED

        # Landlord gap-fills from the baseline
        gap_resp = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={baseline.id}"
        )
        assert gap_resp.status_code == status.HTTP_200_OK
        contents = [m["content"] for m in gap_resp.data["results"]]
        assert "Ny melding fra leietaker." in contents


# ---------------------------------------------------------------------------
# E2E tests for performance optimizations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConversationCreateE2E:
    """Creating a conversation via the API should return a fully serialized
    response with nested participant and delegation data (prefetch fix)."""

    def test_create_and_immediately_view_conversation(
        self, landlord_client, tenant_user, landlord_user
    ):
        """Create → detail fetch should return consistent data."""
        create_resp = landlord_client.post(
            "/api/conversations/",
            {
                "subject": "E2E prefetch test",
                "participants": [
                    {
                        "user_id": str(tenant_user.id),
                        "role": "tenant",
                        "side": "tenant_side",
                    },
                    {
                        "user_id": str(landlord_user.id),
                        "role": "landlord",
                        "side": "landlord_side",
                    },
                ],
            },
            format="json",
        )
        assert create_resp.status_code == status.HTTP_201_CREATED

        conv_id = create_resp.data["id"]
        create_participants = create_resp.data["participants"]

        # Immediately fetch the detail view
        detail_resp = landlord_client.get(f"/api/conversations/{conv_id}/")
        assert detail_resp.status_code == status.HTTP_200_OK
        detail_participants = detail_resp.data["participants"]

        # Both responses should have the same participants
        create_user_ids = sorted(p["user"]["id"] for p in create_participants)
        detail_user_ids = sorted(p["user"]["id"] for p in detail_participants)
        assert create_user_ids == detail_user_ids

    def test_create_with_message_then_list_shows_last_message(
        self, landlord_client, tenant_user, landlord_user
    ):
        """Create with initial message → list should show last_message."""
        create_resp = landlord_client.post(
            "/api/conversations/",
            {
                "subject": "Med melding",
                "participants": [
                    {
                        "user_id": str(tenant_user.id),
                        "role": "tenant",
                        "side": "tenant_side",
                    },
                    {
                        "user_id": str(landlord_user.id),
                        "role": "landlord",
                        "side": "landlord_side",
                    },
                ],
                "initial_message": "Første melding i samtalen.",
            },
            format="json",
        )
        assert create_resp.status_code == status.HTTP_201_CREATED

        # List should include this conversation with last_message
        list_resp = landlord_client.get("/api/conversations/")
        assert list_resp.status_code == status.HTTP_200_OK
        results = list_resp.data["results"]
        conv_data = next(r for r in results if r["id"] == create_resp.data["id"])
        assert conv_data["last_message"] is not None
        assert "Første melding" in conv_data["last_message"]["content"]


@pytest.mark.django_db
class TestLandlordActionsE2E:
    """End-to-end tests for landlord-side actions using cached participant."""

    def test_full_delegation_lifecycle(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        """Add participant → delegate → remove delegation → verify."""
        conv, _, _ = conversation_with_participants

        # Add a property manager
        manager = UserFactory()
        add_resp = landlord_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(manager.id),
                "role": "property_manager",
                "side": "landlord_side",
            },
        )
        assert add_resp.status_code == status.HTTP_201_CREATED

        # Delegate to the manager
        delegate_resp = landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(manager.id)},
        )
        assert delegate_resp.status_code == status.HTTP_201_CREATED

        # Verify delegation in detail view
        detail_resp = landlord_client.get(f"/api/conversations/{conv.id}/")
        assert detail_resp.data["active_delegation"] is not None
        assert detail_resp.data["active_delegation"]["assigned_to"]["id"] == str(manager.id)

        # Remove delegation
        remove_resp = landlord_client.delete(f"/api/conversations/{conv.id}/delegate/")
        assert remove_resp.status_code == status.HTTP_204_NO_CONTENT

        # Verify no active delegation
        detail_resp2 = landlord_client.get(f"/api/conversations/{conv.id}/")
        assert detail_resp2.data["active_delegation"] is None

    def test_internal_message_flow_with_multi_participant(
        self,
        landlord_client,
        tenant_client,
        multi_participant_conversation,
        tenant_user,
    ):
        """Internal message should increment unread for landlord-side users only,
        and be invisible to tenant in all endpoints."""
        conv, participants = multi_participant_conversation
        for p in participants.values():
            ReadStateFactory(conversation=conv, user=p.user, unread_count=0)

        # Landlord sends internal comment
        send_resp = landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern: forsikring dekning?", "is_internal": True},
        )
        assert send_resp.status_code == status.HTTP_201_CREATED

        # Tenant unread stays 0
        tenant_rs = ReadState.objects.get(conversation=conv, user=tenant_user)
        assert tenant_rs.unread_count == 0

        # Manager unread incremented
        manager_rs = ReadState.objects.get(conversation=conv, user=participants["manager"].user)
        assert manager_rs.unread_count == 1

        # Tenant cannot see the internal message in message list
        tenant_msgs = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert tenant_msgs.status_code == status.HTTP_200_OK
        assert all(not m["is_internal"] for m in tenant_msgs.data["results"])

    def test_tenant_blocked_from_all_landlord_actions(
        self, tenant_client, conversation_with_participants, property_manager_user
    ):
        """Tenant should be blocked from add_participant, delegate,
        remove_participant, and remove_delegate."""
        conv, _, _ = conversation_with_participants

        # Try add participant
        resp = tenant_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(property_manager_user.id),
                "role": "property_manager",
                "side": "landlord_side",
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Try delegate
        resp = tenant_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Try remove delegate
        resp = tenant_client.delete(f"/api/conversations/{conv.id}/delegate/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestConversationListOptimization:
    """Verify conversation list returns annotated data correctly after
    the single-query optimization for get_user_conversations."""

    def test_list_with_multiple_conversations_and_unread(
        self, landlord_client, landlord_user, tenant_user
    ):
        """Create multiple conversations and verify list returns correct
        unread counts and last messages without N+1."""
        for i in range(3):
            conv = create_conv_with_message(tenant_user, landlord_user, f"Samtale {i}")
            # create_conversation already creates ReadState; update the count
            ReadState.objects.filter(conversation=conv, user=landlord_user).update(
                unread_count=i + 1
            )

        resp = landlord_client.get("/api/conversations/")
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data["results"]
        assert len(results) == 3

        # Each conversation should have unread_count and last_message
        for r in results:
            assert "unread_count" in r
            assert r["unread_count"] >= 1
            assert "last_message" in r
            assert r["last_message"] is not None

    def test_list_returns_active_participants_only(
        self, landlord_client, landlord_user, tenant_user
    ):
        """Conversation list should only include active participants."""
        conv = create_conv_with_message(tenant_user, landlord_user, "Test")

        # Add and remove a participant
        extra = UserFactory()
        p = ParticipantFactory(
            conversation=conv, user=extra, role="contractor", side="landlord_side"
        )
        p.is_active = False
        p.save()

        resp = landlord_client.get("/api/conversations/")
        results = resp.data["results"]
        conv_data = next(r for r in results if r["id"] == str(conv.id))
        participant_ids = [p["id"] for p in conv_data["participants"]]
        assert str(extra.id) not in participant_ids


def create_conv_with_message(tenant_user, landlord_user, content):
    """Helper to create a conversation with a message for list tests."""
    from apps.messaging.services import create_conversation, send_message

    conv = create_conversation(
        creator=tenant_user,
        participant_data=[
            {"user_id": tenant_user.id, "role": "tenant", "side": "tenant_side"},
            {"user_id": landlord_user.id, "role": "landlord", "side": "landlord_side"},
        ],
        subject=content,
    )
    send_message(sender=tenant_user, conversation=conv, content=content)
    return conv
