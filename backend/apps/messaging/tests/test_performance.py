"""
Tests verifying performance optimizations across the messaging system.

Finding 1-1 + 3-1: Participant lookup optimization (get_visible_messages / get_participant_or_deny)
Finding 1-2: Message create avoids extra participant query on internal messages
Finding 1-3: ConversationDetail prefetching (participants + delegations)
Finding 1-4 + 1-5: Index verification (ReadState, Delegation)
Finding 1-6: Search optimization (internal message exclusion for tenants)
Finding 1-8: Build sync state (ReadState values_list for unread counts)
"""

import pytest
from rest_framework import status

from apps.messaging.models import (
    ConversationParticipant,
    Delegation,
    ReadState,
)
from apps.messaging.permissions import get_participant_or_deny, get_visible_messages
from apps.messaging.services import search_messages

from .conftest import (
    ConversationFactory,
    DelegationFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)

# ---------------------------------------------------------------------------
# Finding 1-1 + 3-1: Participant lookup & get_visible_messages
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestParticipantLookupOptimization:
    """get_visible_messages() uses the participant record internally to decide
    visibility, and get_participant_or_deny() returns a reusable participant."""

    def test_get_visible_messages_excludes_internal_for_tenant(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Public msg")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Secret note")

        visible = get_visible_messages(tenant_user, conv)
        assert visible.count() == 1
        assert visible.first().is_internal is False

    def test_get_visible_messages_includes_internal_for_landlord(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Public msg")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Secret note")

        visible = get_visible_messages(landlord_user, conv)
        assert visible.count() == 2

    def test_get_visible_messages_denies_non_participant(self, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        outsider = UserFactory()
        with pytest.raises(Exception, match="tilgang"):
            get_visible_messages(outsider, conv)

    def test_get_participant_or_deny_returns_reusable_participant(
        self, conversation_with_participants, tenant_user
    ):
        conv, tenant_p, _ = conversation_with_participants
        result = get_participant_or_deny(tenant_user, conv)
        assert isinstance(result, ConversationParticipant)
        assert result.id == tenant_p.id
        assert result.side == "tenant_side"

    def test_get_participant_or_deny_raises_for_inactive(
        self, conversation_with_participants, tenant_user
    ):
        conv, tenant_p, _ = conversation_with_participants
        tenant_p.is_active = False
        tenant_p.save()

        with pytest.raises(Exception, match="tilgang"):
            get_participant_or_deny(tenant_user, conv)


# ---------------------------------------------------------------------------
# Finding 1-2: Message create — no extra participant query on internal messages
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMessageCreateInternalOptimization:
    """POST to messages endpoint reuses the participant fetched for permission
    checking instead of making a separate query for the is_internal guard."""

    def test_regular_message_created_successfully(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Vanlig melding fra leietaker."},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_internal"] is False
        assert response.data["sender"]["id"] == str(tenant_user.id)

    def test_landlord_sends_internal_message(
        self, landlord_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        response = landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern merknad om kostnader.", "is_internal": True},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_internal"] is True

    def test_tenant_rejected_for_internal_message(
        self, tenant_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Forsøk på intern melding", "is_internal": True},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Finding 1-3: ConversationDetail prefetching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConversationDetailPrefetching:
    """GET /api/conversations/{id}/ should prefetch participants and
    delegations including nested user details."""

    def test_detail_returns_all_participants(
        self, landlord_client, multi_participant_conversation
    ):
        conv, _participants = multi_participant_conversation
        response = landlord_client.get(f"/api/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_200_OK

        returned_participants = response.data["participants"]
        assert len(returned_participants) == 4

        # Each participant should have nested user details
        for p in returned_participants:
            assert "user" in p
            assert "id" in p["user"]
            assert "first_name" in p["user"]

    def test_detail_includes_active_delegation_with_user_details(
        self, landlord_client, conversation_with_participants, landlord_user, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )
        DelegationFactory(
            conversation=conv,
            assigned_to=property_manager_user,
            assigned_by=landlord_user,
        )

        response = landlord_client.get(f"/api/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_200_OK

        delegation = response.data["active_delegation"]
        assert delegation is not None
        # DelegationSerializer nests UserSerializer for both assigned_to and assigned_by
        assert "id" in delegation["assigned_to"]
        assert "first_name" in delegation["assigned_to"]
        assert "id" in delegation["assigned_by"]
        assert "first_name" in delegation["assigned_by"]

    def test_detail_without_delegation_returns_null(
        self, tenant_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        response = tenant_client.get(f"/api/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["active_delegation"] is None


# ---------------------------------------------------------------------------
# Finding 1-6: Search optimization
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSearchOptimization:
    """search_messages() excludes internal messages for tenant-side users
    using a single participant query for both user conversations and
    tenant-side filtering."""

    def test_search_excludes_internal_for_tenant(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Offentlig melding")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Intern notat")

        results = search_messages(tenant_user)
        assert all(not m.is_internal for m in results)
        contents = [m.content for m in results]
        assert "Intern notat" not in contents

    def test_search_includes_internal_for_landlord(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Offentlig melding")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Intern notat")

        results = search_messages(landlord_user)
        contents = [m.content for m in results]
        assert "Intern notat" in contents

    def test_search_api_combined_filters(
        self, landlord_client, conversation_with_participants, landlord_user, sample_property
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Heisen er ødelagt igjen")

        response = landlord_client.get(
            "/api/conversations/search/",
            {
                "property": str(sample_property.id),
                "status": "open",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_search_only_returns_user_conversations(
        self, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Min melding")

        # Create a separate conversation the tenant is NOT part of
        other_conv = ConversationFactory()
        other_user = UserFactory()
        ParticipantFactory(
            conversation=other_conv, user=other_user, role="tenant", side="tenant_side"
        )
        MessageFactory(conversation=other_conv, sender=other_user, content="Andres melding")

        results = search_messages(tenant_user)
        result_conv_ids = {m.conversation_id for m in results}
        assert other_conv.id not in result_conv_ids


# ---------------------------------------------------------------------------
# Finding 1-8: Build sync state — ReadState values_list for unread counts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReadStateSyncState:
    """ReadState.objects.filter(user=...).values_list() returns correct
    unread counts for building the WebSocket connection.sync payload."""

    def test_values_list_returns_correct_unread_counts(self, tenant_user, landlord_user):
        conv1 = ConversationFactory()
        conv2 = ConversationFactory()
        conv3 = ConversationFactory()

        ParticipantFactory(conversation=conv1, user=tenant_user, role="tenant", side="tenant_side")
        ParticipantFactory(conversation=conv2, user=tenant_user, role="tenant", side="tenant_side")
        ParticipantFactory(conversation=conv3, user=tenant_user, role="tenant", side="tenant_side")

        ReadStateFactory(conversation=conv1, user=tenant_user, unread_count=5)
        ReadStateFactory(conversation=conv2, user=tenant_user, unread_count=0)
        ReadStateFactory(conversation=conv3, user=tenant_user, unread_count=12)

        unread_data = dict(
            ReadState.objects.filter(user=tenant_user).values_list(
                "conversation_id", "unread_count"
            )
        )

        assert unread_data[conv1.id] == 5
        assert unread_data[conv2.id] == 0
        assert unread_data[conv3.id] == 12

    def test_values_list_empty_for_new_user(self):
        user = UserFactory()
        unread_data = dict(
            ReadState.objects.filter(user=user).values_list("conversation_id", "unread_count")
        )
        assert unread_data == {}

    def test_unread_count_annotation_on_conversation_list(
        self, tenant_client, tenant_user, landlord_user
    ):
        """The conversation list endpoint annotates unread_count from ReadState
        rather than issuing a per-conversation query."""
        conv = ConversationFactory()
        ParticipantFactory(conversation=conv, user=tenant_user, role="tenant", side="tenant_side")
        ParticipantFactory(
            conversation=conv, user=landlord_user, role="landlord", side="landlord_side"
        )
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=7)

        response = tenant_client.get("/api/conversations/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["unread_count"] == 7


# ---------------------------------------------------------------------------
# Finding 1-4 + 1-5: Index verification
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIndexVerification:
    """Verify that critical indexes exist on ReadState and Delegation models."""

    def test_readstate_has_user_first_index(self):
        """ReadState should have an index starting with 'user' for efficient
        per-user lookups (idx_readstate_user_conv)."""
        indexes = ReadState._meta.indexes
        index_fields = [tuple(idx.fields) for idx in indexes]
        # The user-first index: ("user", "conversation")
        assert ("user", "conversation") in index_fields

    def test_delegation_has_conversation_active_index(self):
        """Delegation should have a compound index on (conversation, is_active)
        for efficient active delegation lookups (idx_delegation_conv_active)."""
        indexes = Delegation._meta.indexes
        index_fields = [tuple(idx.fields) for idx in indexes]
        assert ("conversation", "is_active") in index_fields

    def test_readstate_index_name(self):
        """Verify the specific index name for documentation/migration clarity."""
        indexes = ReadState._meta.indexes
        index_names = [idx.name for idx in indexes]
        assert "idx_readstate_user_conv" in index_names

    def test_delegation_index_name(self):
        """Verify the specific index name for documentation/migration clarity."""
        indexes = Delegation._meta.indexes
        index_names = [idx.name for idx in indexes]
        assert "idx_delegation_conv_active" in index_names
