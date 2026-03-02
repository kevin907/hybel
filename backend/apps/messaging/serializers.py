from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import (
    Attachment,
    Conversation,
    ConversationParticipant,
    ConversationType,
    Delegation,
    Message,
    ParticipantRole,
    ParticipantSide,
    ReadState,
)


class AttachmentSerializer(serializers.ModelSerializer[Attachment]):
    class Meta:
        model = Attachment
        fields = ["id", "filename", "file_type", "file_size", "uploaded_at"]
        read_only_fields = fields


class ParticipantSerializer(serializers.ModelSerializer[ConversationParticipant]):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = ["id", "user", "role", "side", "is_active", "joined_at", "left_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer[Message]):
    sender = UserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "message_type",
            "is_internal",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DelegationSerializer(serializers.ModelSerializer[Delegation]):
    assigned_to = UserSerializer(read_only=True)
    assigned_by = UserSerializer(read_only=True)

    class Meta:
        model = Delegation
        fields = [
            "id",
            "assigned_to",
            "assigned_by",
            "note",
            "is_active",
            "assigned_at",
        ]
        read_only_fields = fields


class ConversationListSerializer(serializers.ModelSerializer[Conversation]):
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
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
        ]
        read_only_fields = fields

    def get_unread_count(self, obj: Conversation) -> int:
        # Use annotated value from queryset (avoids N+1)
        if hasattr(obj, "annotated_unread"):
            return obj.annotated_unread  # type: ignore[no-any-return]
        user = self.context["request"].user
        try:
            rs = ReadState.objects.get(conversation=obj, user=user)
            return rs.unread_count
        except ReadState.DoesNotExist:
            return 0

    def get_last_message(self, obj: Conversation) -> dict[str, Any] | None:
        # Use batch-fetched messages from context (avoids N+1)
        last_messages = self.context.get("last_messages", {})
        msg_id = getattr(obj, "annotated_last_message_id", None)
        if msg_id and msg_id in last_messages:
            last = last_messages[msg_id]
            return {
                "id": str(last.id),
                "content": last.content[:100],
                "sender": UserSerializer(last.sender).data,
                "created_at": last.created_at.isoformat(),
                "is_internal": last.is_internal,
            }

        # Fallback for non-list contexts (e.g. detail)
        if msg_id is None:
            user = self.context["request"].user
            last = (
                Message.objects.visible_to(user, obj)
                .select_related("sender")
                .order_by("-created_at")
                .first()
            )
            if not last:
                return None
            return {
                "id": str(last.id),
                "content": last.content[:100],
                "sender": UserSerializer(last.sender).data,
                "created_at": last.created_at.isoformat(),
                "is_internal": last.is_internal,
            }
        return None

    def get_participants(self, obj: Conversation) -> list[dict[str, Any]]:
        # Use prefetched active_participants if available (avoids N+1 + Python filtering)
        participants = getattr(obj, "active_participants", None)
        if participants is None:
            participants = [p for p in obj.participants.all() if p.is_active]
        return [
            {
                "id": str(p.user.id),
                "name": f"{p.user.first_name} {p.user.last_name}",
                "role": p.role,
                "side": p.side,
            }
            for p in participants
        ]


class ConversationDetailSerializer(serializers.ModelSerializer[Conversation]):
    participants = ParticipantSerializer(many=True, read_only=True)
    active_delegation = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "subject",
            "conversation_type",
            "status",
            "property",
            "participants",
            "active_delegation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_active_delegation(self, obj: Conversation) -> dict[str, Any] | None:
        delegation = obj.delegations.filter(is_active=True).first()
        if not delegation:
            return None
        return DelegationSerializer(delegation).data


class AddParticipantSerializer(serializers.Serializer[dict[str, Any]]):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=ParticipantRole.choices)
    side = serializers.ChoiceField(choices=ParticipantSide.choices)


class CreateMessageSerializer(serializers.Serializer[dict[str, Any]]):
    content = serializers.CharField()
    is_internal = serializers.BooleanField(default=False)


class CreateConversationSerializer(serializers.Serializer[dict[str, Any]]):
    subject = serializers.CharField(required=False, allow_blank=True, default="")
    conversation_type = serializers.ChoiceField(
        choices=ConversationType.choices,
        default="general",
    )
    property_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    participants = AddParticipantSerializer(many=True, allow_empty=False)
    initial_message = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateConversationSerializer(serializers.ModelSerializer[Conversation]):
    class Meta:
        model = Conversation
        fields = ["subject", "status"]


class DelegateSerializer(serializers.Serializer[dict[str, Any]]):
    assigned_to = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True, default="")


class MarkReadSerializer(serializers.Serializer[dict[str, Any]]):
    last_read_message_id = serializers.UUIDField()


class SearchQuerySerializer(serializers.Serializer[dict[str, Any]]):
    q = serializers.CharField(required=False, allow_blank=True, default="")
    property = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=["open", "closed", "archived"], required=False)
    conversation_type = serializers.ChoiceField(choices=ConversationType.choices, required=False)
    has_attachment = serializers.BooleanField(required=False, default=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    unread_only = serializers.BooleanField(required=False, default=False)


class MessageSearchResultSerializer(serializers.ModelSerializer[Message]):
    sender = UserSerializer(read_only=True)
    conversation_id = serializers.UUIDField(source="conversation.id")
    conversation_subject = serializers.CharField(source="conversation.subject")
    snippet = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation_id",
            "conversation_subject",
            "sender",
            "content",
            "snippet",
            "message_type",
            "is_internal",
            "created_at",
        ]
        read_only_fields = fields

    def get_snippet(self, obj: Message) -> str:
        if hasattr(obj, "headline"):
            return str(obj.headline)
        return obj.content[:150]
