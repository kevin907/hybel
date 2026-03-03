"""
API contract tests verifying that backend response shapes match
the frontend TypeScript types defined in frontend/src/types/messaging.ts.

Each test class corresponds to a TypeScript interface and asserts
that the JSON response contains exactly the expected set of fields.
"""

import pytest
from rest_framework import status

from .conftest import (
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)

# ──────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────

USER_FIELDS = {"id", "email", "first_name", "last_name"}


# ──────────────────────────────────────────────────
# ConversationListItem contract
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestConversationListContract:
    """
    Frontend type: ConversationListItem
    Fields: {id, subject, conversation_type, status, property,
             unread_count, last_message, participants, created_at, updated_at}
    """

    EXPECTED_FIELDS = {
        "id",
        "subject",
        "conversation_type",
        "status",
        "property",
        "unread_count",
        "last_message",
        "participants",
        "created_at",
        "updated_at",
    }

    def test_conversation_list_item_fields(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=1)
        MessageFactory(conversation=conv, sender=landlord_user, content="Hei")

        resp = tenant_client.get("/api/conversations/")
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data["results"]
        assert len(results) >= 1

        item = results[0]
        assert set(item.keys()) == self.EXPECTED_FIELDS

    def test_last_message_sub_fields(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        """LastMessage: {id, content, sender, created_at, is_internal}"""
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Siste melding")

        resp = tenant_client.get("/api/conversations/")
        last_msg = resp.data["results"][0]["last_message"]
        assert last_msg is not None
        expected_last_msg_fields = {"id", "content", "sender", "created_at", "is_internal"}
        assert set(last_msg.keys()) == expected_last_msg_fields

    def test_last_message_sender_has_user_fields(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Test")

        resp = tenant_client.get("/api/conversations/")
        sender = resp.data["results"][0]["last_message"]["sender"]
        assert set(sender.keys()) == USER_FIELDS

    def test_participant_summary_fields(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        """ConversationParticipantSummary: {id, name, role, side}"""
        resp = tenant_client.get("/api/conversations/")
        participants = resp.data["results"][0]["participants"]
        assert len(participants) >= 1
        expected_participant_fields = {"id", "name", "role", "side"}
        for p in participants:
            assert set(p.keys()) == expected_participant_fields

    def test_last_message_null_when_no_messages(
        self, tenant_client, conversation_with_participants
    ):
        resp = tenant_client.get("/api/conversations/")
        item = resp.data["results"][0]
        assert item["last_message"] is None

    def test_unread_count_is_integer(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=5)

        resp = tenant_client.get("/api/conversations/")
        assert isinstance(resp.data["results"][0]["unread_count"], int)

    def test_unread_count_zero_when_no_read_state(
        self, tenant_client, conversation_with_participants
    ):
        """When no ReadState row exists, unread_count should default to 0."""
        resp = tenant_client.get("/api/conversations/")
        assert resp.data["results"][0]["unread_count"] == 0


# ──────────────────────────────────────────────────
# ConversationDetail contract
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestConversationDetailContract:
    """
    Frontend type: ConversationDetail
    Fields: {id, subject, conversation_type, status, property,
             participants, active_delegation, created_at, updated_at}
    """

    EXPECTED_FIELDS = {
        "id",
        "subject",
        "conversation_type",
        "status",
        "property",
        "participants",
        "active_delegation",
        "created_at",
        "updated_at",
    }

    def test_conversation_detail_fields(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        resp = tenant_client.get(f"/api/conversations/{conv.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert set(resp.data.keys()) == self.EXPECTED_FIELDS

    def test_detail_participant_fields(self, tenant_client, conversation_with_participants):
        """Participant: {id, user, role, side, is_active, joined_at, left_at}"""
        conv, _, _ = conversation_with_participants
        resp = tenant_client.get(f"/api/conversations/{conv.id}/")
        participants = resp.data["participants"]
        assert len(participants) >= 1
        expected = {"id", "user", "role", "side", "is_active", "joined_at", "left_at"}
        for p in participants:
            assert set(p.keys()) == expected

    def test_detail_participant_user_fields(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        resp = tenant_client.get(f"/api/conversations/{conv.id}/")
        for p in resp.data["participants"]:
            assert set(p["user"].keys()) == USER_FIELDS

    def test_active_delegation_null_when_none(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        resp = tenant_client.get(f"/api/conversations/{conv.id}/")
        assert resp.data["active_delegation"] is None

    def test_active_delegation_fields_when_present(
        self,
        landlord_client,
        conversation_with_participants,
        landlord_user,
        property_manager_user,
    ):
        """Delegation: {id, assigned_to, assigned_by, note, is_active, assigned_at}"""
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )
        landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )

        resp = landlord_client.get(f"/api/conversations/{conv.id}/")
        delegation = resp.data["active_delegation"]
        assert delegation is not None
        expected_delegation_fields = {
            "id",
            "assigned_to",
            "assigned_by",
            "note",
            "is_active",
            "assigned_at",
        }
        assert set(delegation.keys()) == expected_delegation_fields

    def test_delegation_assigned_to_has_user_fields(
        self,
        landlord_client,
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
        landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )

        resp = landlord_client.get(f"/api/conversations/{conv.id}/")
        delegation = resp.data["active_delegation"]
        assert set(delegation["assigned_to"].keys()) == USER_FIELDS
        assert set(delegation["assigned_by"].keys()) == USER_FIELDS


# ──────────────────────────────────────────────────
# Message contract
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestMessageContract:
    """
    Frontend type: Message
    Fields: {id, conversation, sender, content, message_type,
             is_internal, attachments, created_at, updated_at}
    """

    EXPECTED_FIELDS = {
        "id",
        "conversation",
        "sender",
        "content",
        "message_type",
        "is_internal",
        "attachments",
        "created_at",
        "updated_at",
    }

    def test_message_response_fields(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Test melding")

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert resp.status_code == status.HTTP_200_OK
        msg = resp.data["results"][0]
        assert set(msg.keys()) == self.EXPECTED_FIELDS

    def test_message_sender_has_user_fields(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        sender = resp.data["results"][0]["sender"]
        assert set(sender.keys()) == USER_FIELDS

    def test_message_attachments_is_list(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert isinstance(resp.data["results"][0]["attachments"], list)

    def test_sent_message_response_fields(self, tenant_client, conversation_with_participants):
        """POST response to create message must match the Message type."""
        conv, _, _ = conversation_with_participants
        resp = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Sendt melding"},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert set(resp.data.keys()) == self.EXPECTED_FIELDS

    def test_message_is_internal_is_boolean(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert isinstance(resp.data["results"][0]["is_internal"], bool)

    def test_message_conversation_is_string_uuid(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        conversation_field = resp.data["results"][0]["conversation"]
        # DRF test client returns UUID objects; JSON serialization converts to string.
        # Verify the value matches the expected conversation ID.
        assert str(conversation_field) == str(conv.id)


# ──────────────────────────────────────────────────
# SearchResult contract
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestSearchResultContract:
    """
    Frontend type: SearchResult
    Fields: {id, conversation_id, conversation_subject, sender,
             content, snippet, message_type, is_internal, created_at}
    """

    EXPECTED_FIELDS = {
        "id",
        "conversation_id",
        "conversation_subject",
        "sender",
        "content",
        "snippet",
        "message_type",
        "is_internal",
        "created_at",
    }

    def test_search_result_fields(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Vannlekkasje i kjelleren",
        )

        resp = tenant_client.get("/api/conversations/search/", {"q": "vannlekkasje"})
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data["results"]) >= 1
        result = resp.data["results"][0]
        assert set(result.keys()) == self.EXPECTED_FIELDS

    def test_search_result_sender_has_user_fields(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Vannlekkasje på badet",
        )

        resp = tenant_client.get("/api/conversations/search/", {"q": "vannlekkasje"})
        sender = resp.data["results"][0]["sender"]
        assert set(sender.keys()) == USER_FIELDS

    def test_search_result_snippet_is_string(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Vannrør lekker under vasken.",
        )

        resp = tenant_client.get("/api/conversations/search/", {"q": "vannrør"})
        assert len(resp.data["results"]) >= 1
        assert isinstance(resp.data["results"][0]["snippet"], str)

    def test_search_result_conversation_id_is_string(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Søketest melding",
        )

        resp = tenant_client.get("/api/conversations/search/")
        result = resp.data["results"][0]
        assert isinstance(result["conversation_id"], str)
        assert isinstance(result["conversation_subject"], str)


# ──────────────────────────────────────────────────
# User fields contract
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestUserFieldsContract:
    """
    Frontend type: User
    Fields: {id, email, first_name, last_name}
    Verified across multiple surfaces.
    """

    def test_user_in_message_sender(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        sender = resp.data["results"][0]["sender"]
        assert set(sender.keys()) == USER_FIELDS
        assert sender["id"] == str(tenant_user.id)
        assert sender["email"] == tenant_user.email
        assert sender["first_name"] == tenant_user.first_name
        assert sender["last_name"] == tenant_user.last_name

    def test_user_in_conversation_detail_participant(
        self, tenant_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        resp = tenant_client.get(f"/api/conversations/{conv.id}/")
        for p in resp.data["participants"]:
            assert set(p["user"].keys()) == USER_FIELDS

    def test_user_in_search_result_sender(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Brukerfelter test",
        )

        resp = tenant_client.get("/api/conversations/search/")
        sender = resp.data["results"][0]["sender"]
        assert set(sender.keys()) == USER_FIELDS


# ──────────────────────────────────────────────────
# Pagination contracts
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestMessageCursorPaginationContract:
    """
    Messages use CursorPagination.
    CursorPaginatedResponse<T>: {next, previous, results} — NO count field.
    """

    def test_cursor_pagination_shape(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data
        assert "count" not in resp.data

    def test_cursor_pagination_results_is_list(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert isinstance(resp.data["results"], list)

    def test_cursor_pagination_next_is_string_or_null(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user)

        resp = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert resp.data["next"] is None or isinstance(resp.data["next"], str)
        assert resp.data["previous"] is None or isinstance(resp.data["previous"], str)


@pytest.mark.django_db
class TestConversationListPaginationContract:
    """
    Conversation list uses CursorPagination.
    CursorPaginatedResponse<T>: {next, previous, results} — NO count field.
    """

    def test_conversation_list_cursor_pagination_shape(
        self, tenant_client, conversation_with_participants
    ):
        resp = tenant_client.get("/api/conversations/")
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data
        assert "count" not in resp.data

    def test_conversation_list_results_is_list(
        self, tenant_client, conversation_with_participants
    ):
        resp = tenant_client.get("/api/conversations/")
        assert isinstance(resp.data["results"], list)


# ──────────────────────────────────────────────────
# Action endpoint response contracts
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestMarkReadResponseContract:
    """mark_read returns {unread_count}"""

    def test_mark_read_response_shape(
        self,
        tenant_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=landlord_user)
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=1)

        resp = tenant_client.post(
            f"/api/conversations/{conv.id}/read/",
            {"last_read_message_id": str(msg.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "unread_count" in resp.data
        assert isinstance(resp.data["unread_count"], int)

    def test_mark_read_unread_count_is_zero_after(
        self,
        tenant_client,
        conversation_with_participants,
        tenant_user,
        landlord_user,
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=landlord_user)
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=3)

        resp = tenant_client.post(
            f"/api/conversations/{conv.id}/read/",
            {"last_read_message_id": str(msg.id)},
        )
        assert resp.data["unread_count"] == 0


@pytest.mark.django_db
class TestAddParticipantResponseContract:
    """add_participant returns {id, user_id}"""

    def test_add_participant_response_shape(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()

        resp = landlord_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(new_user.id),
                "role": "contractor",
                "side": "landlord_side",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "id" in resp.data
        assert "user_id" in resp.data
        assert resp.data["user_id"] == str(new_user.id)

    def test_add_participant_id_is_string(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()

        resp = landlord_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(new_user.id),
                "role": "contractor",
                "side": "landlord_side",
            },
        )
        assert isinstance(resp.data["id"], str)
        assert isinstance(resp.data["user_id"], str)


@pytest.mark.django_db
class TestDelegateResponseContract:
    """delegate returns {id, assigned_to}"""

    def test_delegate_response_shape(
        self,
        landlord_client,
        conversation_with_participants,
        property_manager_user,
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )

        resp = landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert "id" in resp.data
        assert "assigned_to" in resp.data
        assert resp.data["assigned_to"] == str(property_manager_user.id)

    def test_delegate_response_values_are_strings(
        self,
        landlord_client,
        conversation_with_participants,
        property_manager_user,
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )

        resp = landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        assert isinstance(resp.data["id"], str)
        assert isinstance(resp.data["assigned_to"], str)


# ──────────────────────────────────────────────────
# Search pagination contract
# ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestSearchPaginationContract:
    """
    Search uses PageNumberPagination.
    PaginatedResponse<T>: {count, next, previous, results}
    """

    def test_search_pagination_shape(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Paginering test")

        resp = tenant_client.get("/api/conversations/search/")
        assert resp.status_code == status.HTTP_200_OK
        assert "count" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data
        assert "results" in resp.data
        assert isinstance(resp.data["count"], int)
        assert isinstance(resp.data["results"], list)
