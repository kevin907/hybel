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
    ReadStateFactory,
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
        contents = [m["content"] for m in tenant_resp.data]
        assert "Intern merknad om leietaker." not in contents
        assert "Offentlig svar." in contents
        assert all(not m["is_internal"] for m in tenant_resp.data)

        # Landlord gap-fills from m1 — should see the internal comment
        landlord_resp = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        landlord_contents = [m["content"] for m in landlord_resp.data]
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
        ids = [m["id"] for m in resp.data]
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
        assert len(resp.data) == 0

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
        contents = [m["content"] for m in resp.data]
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
        contents = [m["content"] for m in gap_resp.data]
        assert "Ny melding fra leietaker." in contents
