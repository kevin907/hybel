from django.contrib import admin

from .models import (
    Attachment,
    Conversation,
    ConversationParticipant,
    Delegation,
    Message,
    ReadState,
)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "id",
        "subject",
        "conversation_type",
        "status",
        "property",
        "updated_at",
    ]
    list_filter = ["status", "conversation_type"]
    search_fields = ["subject"]


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["conversation", "user", "role", "side", "is_active"]
    list_filter = ["role", "side", "is_active"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "id",
        "conversation",
        "sender",
        "message_type",
        "is_internal",
        "created_at",
    ]
    list_filter = ["message_type", "is_internal"]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "filename", "file_type", "file_size", "uploaded_at"]


@admin.register(ReadState)
class ReadStateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["conversation", "user", "unread_count", "last_read_at"]


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "conversation",
        "assigned_to",
        "assigned_by",
        "is_active",
        "assigned_at",
    ]
    list_filter = ["is_active"]
