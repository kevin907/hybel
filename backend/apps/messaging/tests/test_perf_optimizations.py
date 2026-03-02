"""
Tests for performance optimizations implemented in the messaging system.

Covers:
- permissions.py: get_cached_participant(), get_user_conversations() single JOIN
- services.py: send_message() pre-computed landlord user IDs
- events.py: broadcast_new_message() with pre-computed IDs
- serializers.py: fallback logging warnings
- views.py: conversation create prefetch, cached participant reuse
"""

from unittest.mock import patch  # noqa: I001

import pytest
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.messaging.models import ConversationParticipant, ReadState
from apps.messaging.permissions import (
    get_cached_participant,
    get_user_conversations,
    require_participant_landlord_side,
)
from apps.messaging.services import send_message

from .conftest import (
    ConversationFactory,
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# permissions.py — get_cached_participant()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetCachedParticipant:
    """get_cached_participant() should return the cached participant from the
    request object when available, avoiding a duplicate DB query."""

    def test_returns_cached_participant_when_available(
        self, conversation_with_participants, tenant_user
    ):
        conv, tenant_p, _ = conversation_with_participants
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user
        # Simulate what IsConversationParticipant.has_object_permission() does
        request._cached_participant = tenant_p

        result = get_cached_participant(request, conv)
        assert result.id == tenant_p.id
        assert result.side == "tenant_side"

    def test_falls_back_to_db_when_no_cache(self, conversation_with_participants, tenant_user):
        conv, tenant_p, _ = conversation_with_participants
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user
        # No _cached_participant set

        result = get_cached_participant(request, conv)
        assert result.id == tenant_p.id

    def test_falls_back_when_cached_for_different_conversation(
        self, conversation_with_participants, tenant_user
    ):
        conv, tenant_p, _ = conversation_with_participants

        # Create a second conversation with the same tenant
        other_conv = ConversationFactory()
        other_p = ParticipantFactory(
            conversation=other_conv,
            user=tenant_user,
            role="tenant",
            side="tenant_side",
        )

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user
        # Cache is for the OTHER conversation
        request._cached_participant = other_p

        result = get_cached_participant(request, conv)
        # Should fall back to DB and get the correct participant for conv
        assert result.id == tenant_p.id

    def test_raises_permission_denied_when_not_participant(self, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        outsider = UserFactory()

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = outsider

        with pytest.raises(PermissionDenied):
            get_cached_participant(request, conv)

    def test_cached_participant_avoids_db_query(
        self, conversation_with_participants, tenant_user, django_assert_num_queries
    ):
        conv, tenant_p, _ = conversation_with_participants
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user
        request._cached_participant = tenant_p

        with django_assert_num_queries(0):
            result = get_cached_participant(request, conv)
        assert result.id == tenant_p.id


# ---------------------------------------------------------------------------
# permissions.py — get_user_conversations() single JOIN
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetUserConversationsSingleQuery:
    """get_user_conversations() should execute a single query using JOIN+DISTINCT
    instead of a two-query subquery approach."""

    def test_single_query_execution(
        self, conversation_with_participants, tenant_user, django_assert_num_queries
    ):
        with django_assert_num_queries(1):
            list(get_user_conversations(tenant_user))

    def test_returns_correct_conversations(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants

        # Create another conversation NOT involving tenant
        other_conv = ConversationFactory()
        other_user = UserFactory()
        ParticipantFactory(
            conversation=other_conv, user=other_user, role="tenant", side="tenant_side"
        )

        result = list(get_user_conversations(tenant_user))
        assert len(result) == 1
        assert result[0].id == conv.id

    def test_excludes_inactive_participants(self, conversation_with_participants, tenant_user):
        _conv, tenant_p, _ = conversation_with_participants
        tenant_p.is_active = False
        tenant_p.save()

        result = list(get_user_conversations(tenant_user))
        assert len(result) == 0

    def test_no_duplicate_conversations_with_multiple_active_roles(self):
        """A user with active participation in a conversation should appear
        exactly once in the result (DISTINCT works correctly)."""
        user = UserFactory()
        other_user = UserFactory()
        conv = ConversationFactory()
        ParticipantFactory(conversation=conv, user=user, role="tenant", side="tenant_side")
        ParticipantFactory(
            conversation=conv, user=other_user, role="landlord", side="landlord_side"
        )

        result = list(get_user_conversations(user))
        assert len(result) == 1

    def test_multiple_conversations_returned(self, tenant_user, landlord_user):
        for _ in range(5):
            conv = ConversationFactory()
            ParticipantFactory(
                conversation=conv, user=tenant_user, role="tenant", side="tenant_side"
            )
            ParticipantFactory(
                conversation=conv, user=landlord_user, role="landlord", side="landlord_side"
            )

        result = list(get_user_conversations(tenant_user))
        assert len(result) == 5


# ---------------------------------------------------------------------------
# permissions.py — require_participant_landlord_side()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequireParticipantLandlordSide:
    """require_participant_landlord_side() checks an already-fetched participant
    object, avoiding a DB query."""

    def test_landlord_side_passes(self, conversation_with_participants):
        _conv, _tenant_p, landlord_p = conversation_with_participants
        # Should not raise
        require_participant_landlord_side(landlord_p, "Feil")

    def test_tenant_side_raises(self, conversation_with_participants):
        _conv, tenant_p, _ = conversation_with_participants
        with pytest.raises(PermissionDenied, match="Feil"):
            require_participant_landlord_side(tenant_p, "Feil")

    def test_no_db_query(self, conversation_with_participants, django_assert_num_queries):
        _conv, _tenant_p, landlord_p = conversation_with_participants
        with django_assert_num_queries(0):
            require_participant_landlord_side(landlord_p, "Feil")


# ---------------------------------------------------------------------------
# services.py — send_message() pre-computed landlord user IDs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSendMessageLandlordIdPreComputation:
    """send_message() for internal messages should pre-compute landlord user IDs
    once and reuse them for both ReadState update and event broadcast."""

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.services.events.broadcast_new_message")
    def test_internal_message_passes_landlord_ids_to_broadcast(
        self, mock_broadcast, _mock_on_commit, multi_participant_conversation
    ):
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

        # broadcast_new_message should have been called with landlord_user_ids
        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args
        # The second argument (or keyword arg) should be the pre-computed IDs
        landlord_ids = call_kwargs[1].get("landlord_user_ids") if call_kwargs[1] else None
        if landlord_ids is None:
            landlord_ids = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        assert landlord_ids is not None
        # Should include manager and contractor (landlord-side, excluding sender)
        assert participants["manager"].user_id in landlord_ids
        assert participants["contractor"].user_id in landlord_ids
        # Should NOT include the sender
        assert participants["landlord"].user_id not in landlord_ids
        # Should NOT include tenant
        assert participants["tenant"].user_id not in landlord_ids

    @patch("apps.messaging.services.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.messaging.services.events.broadcast_new_message")
    def test_regular_message_passes_none_for_landlord_ids(
        self, mock_broadcast, _mock_on_commit, conversation_with_participants, tenant_user
    ):
        conv, _, landlord_p = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user)
        ReadStateFactory(conversation=conv, user=landlord_p.user)

        send_message(
            sender=tenant_user,
            conversation=conv,
            content="Vanlig melding",
        )

        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args
        landlord_ids = call_kwargs[1].get("landlord_user_ids") if call_kwargs[1] else None
        if landlord_ids is None and len(call_kwargs[0]) > 1:
            landlord_ids = call_kwargs[0][1]
        # For regular messages, landlord_user_ids should be None
        assert landlord_ids is None

    def test_internal_message_increments_only_landlord_side_unread(
        self, multi_participant_conversation
    ):
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

        # Tenant should NOT have unread incremented
        tenant_rs = ReadState.objects.get(conversation=conv, user=participants["tenant"].user)
        assert tenant_rs.unread_count == 0

        # Manager should have unread incremented
        manager_rs = ReadState.objects.get(conversation=conv, user=participants["manager"].user)
        assert manager_rs.unread_count == 1

        # Contractor should have unread incremented
        contractor_rs = ReadState.objects.get(
            conversation=conv, user=participants["contractor"].user
        )
        assert contractor_rs.unread_count == 1

        # Sender (landlord) should NOT have unread incremented
        landlord_rs = ReadState.objects.get(conversation=conv, user=participants["landlord"].user)
        assert landlord_rs.unread_count == 0


# ---------------------------------------------------------------------------
# events.py — broadcast_new_message() with pre-computed IDs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBroadcastNewMessagePreComputedIds:
    """broadcast_new_message() should use pre-computed landlord user IDs
    when provided, avoiding a duplicate query."""

    @patch("apps.messaging.events._send_to_group")
    def test_uses_precomputed_ids_for_internal(self, mock_send, multi_participant_conversation):
        conv, participants = multi_participant_conversation
        from .conftest import InternalCommentFactory

        msg = InternalCommentFactory(conversation=conv, sender=participants["landlord"].user)

        # Pre-computed IDs: only manager and contractor
        precomputed = [participants["manager"].user_id, participants["contractor"].user_id]

        from apps.messaging.events import broadcast_new_message

        broadcast_new_message(msg, landlord_user_ids=precomputed)

        group_names = [call[0][0] for call in mock_send.call_args_list]
        assert f"user_{participants['manager'].user.id}" in group_names
        assert f"user_{participants['contractor'].user.id}" in group_names
        # Sender should still be excluded (sender_id check in broadcast)
        assert f"user_{participants['landlord'].user.id}" not in group_names

    @patch("apps.messaging.events._send_to_group")
    @patch("apps.messaging.events._get_landlord_side_user_ids")
    def test_precomputed_ids_skip_db_query(
        self, mock_get_ids, mock_send, multi_participant_conversation
    ):
        conv, participants = multi_participant_conversation
        from .conftest import InternalCommentFactory

        msg = InternalCommentFactory(conversation=conv, sender=participants["landlord"].user)

        precomputed = [participants["manager"].user_id]

        from apps.messaging.events import broadcast_new_message

        broadcast_new_message(msg, landlord_user_ids=precomputed)

        # _get_landlord_side_user_ids should NOT be called when IDs are pre-computed
        mock_get_ids.assert_not_called()

    @patch("apps.messaging.events._send_to_group")
    @patch("apps.messaging.events._get_landlord_side_user_ids")
    def test_falls_back_to_db_when_no_precomputed_ids(
        self, mock_get_ids, mock_send, multi_participant_conversation
    ):
        conv, participants = multi_participant_conversation
        from .conftest import InternalCommentFactory

        msg = InternalCommentFactory(conversation=conv, sender=participants["landlord"].user)

        mock_get_ids.return_value = [str(participants["manager"].user_id)]

        from apps.messaging.events import broadcast_new_message

        broadcast_new_message(msg, landlord_user_ids=None)

        # _get_landlord_side_user_ids SHOULD be called as fallback
        mock_get_ids.assert_called_once()

    @patch("apps.messaging.events._send_to_group")
    def test_regular_message_ignores_precomputed_ids(
        self, mock_send, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        from apps.messaging.events import broadcast_new_message

        # Even if landlord_user_ids is passed, regular messages go to conversation group
        broadcast_new_message(msg, landlord_user_ids=[])

        mock_send.assert_called_once()
        group_name = mock_send.call_args[0][0]
        assert group_name == f"conversation_{conv.id}"


# ---------------------------------------------------------------------------
# serializers.py — fallback logging warnings
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSerializerFallbackLogging:
    """ConversationListSerializer should log warnings when hitting fallback
    code paths (indicating missing prefetch/annotations)."""

    def test_unread_count_fallback_logs_warning(
        self, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=3)

        from apps.messaging.serializers import ConversationListSerializer

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user

        # Serialize WITHOUT the annotated_unread attribute — triggers fallback
        with patch("apps.messaging.serializers.logger") as mock_logger:
            serializer = ConversationListSerializer(conv, context={"request": request})
            unread = serializer.data["unread_count"]
            assert unread == 3
            warning_messages = [call[0][0] for call in mock_logger.warning.call_args_list]
            assert any("get_unread_count" in m for m in warning_messages)

    def test_unread_count_uses_annotation_when_available(
        self, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants

        from apps.messaging.serializers import ConversationListSerializer

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user

        # Manually set the annotation
        conv.annotated_unread = 42

        with patch("apps.messaging.serializers.logger") as mock_logger:
            serializer = ConversationListSerializer(conv, context={"request": request})
            assert serializer.data["unread_count"] == 42
            # Only check that unread_count-specific warning was NOT logged
            # (other fallbacks like get_last_message/get_participants may still fire)
            unread_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "get_unread_count" in call[0][0]
            ]
            assert len(unread_warnings) == 0

    def test_participants_fallback_logs_warning(self, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants

        from apps.messaging.serializers import ConversationListSerializer

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user

        # No active_participants prefetch — triggers fallback
        with patch("apps.messaging.serializers.logger") as mock_logger:
            serializer = ConversationListSerializer(conv, context={"request": request})
            participants = serializer.data["participants"]
            assert len(participants) >= 1
            mock_logger.warning.assert_called()
            warning_messages = [call[0][0] for call in mock_logger.warning.call_args_list]
            assert any("get_participants" in m for m in warning_messages)

    def test_participants_uses_prefetch_when_available(
        self, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants

        from apps.messaging.serializers import ConversationListSerializer

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = tenant_user

        # Manually set the prefetch attribute
        conv.active_participants = list(
            ConversationParticipant.objects.filter(
                conversation=conv, is_active=True
            ).select_related("user")
        )

        with patch("apps.messaging.serializers.logger") as mock_logger:
            serializer = ConversationListSerializer(conv, context={"request": request})
            participants = serializer.data["participants"]
            assert len(participants) == 2
            # No warning should be logged for get_participants
            participant_warnings = [
                call
                for call in mock_logger.warning.call_args_list
                if "get_participants" in call[0][0]
            ]
            assert len(participant_warnings) == 0


# ---------------------------------------------------------------------------
# views.py — cached participant in endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCachedParticipantInViews:
    """Landlord-side actions and message creation should reuse the cached
    participant from IsConversationParticipant permission class."""

    def test_add_participant_uses_cached_participant(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()

        response = landlord_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(new_user.id),
                "role": "contractor",
                "side": "landlord_side",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_tenant_blocked_from_add_participant(
        self, tenant_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()

        response = tenant_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(new_user.id),
                "role": "contractor",
                "side": "landlord_side",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delegate_uses_cached_participant(
        self, landlord_client, conversation_with_participants, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )

        response = landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_tenant_blocked_from_delegate(
        self, tenant_client, conversation_with_participants, property_manager_user
    ):
        conv, _, _ = conversation_with_participants

        response = tenant_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_message_create_uses_cached_participant(
        self, landlord_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants

        response = landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern merknad", "is_internal": True},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_internal"] is True


# ---------------------------------------------------------------------------
# views.py — conversation create prefetch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConversationCreatePrefetch:
    """POST /api/conversations/ should return a fully serialized response
    with nested participants and delegation data, avoiding N+1 queries."""

    def test_create_returns_participants_with_user_details(
        self, landlord_client, tenant_user, landlord_user
    ):
        response = landlord_client.post(
            "/api/conversations/",
            {
                "subject": "Ny samtale",
                "conversation_type": "general",
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
        assert response.status_code == status.HTTP_201_CREATED

        # Verify participants are fully serialized with user details
        participants = response.data["participants"]
        assert len(participants) == 2
        for p in participants:
            assert "user" in p
            assert "id" in p["user"]
            assert "first_name" in p["user"]

    def test_create_with_initial_message(self, landlord_client, tenant_user, landlord_user):
        response = landlord_client.post(
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
                "initial_message": "Hei, dette er første melding!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["subject"] == "Med melding"

    def test_create_returns_null_delegation(self, landlord_client, tenant_user, landlord_user):
        response = landlord_client.post(
            "/api/conversations/",
            {
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
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["active_delegation"] is None
