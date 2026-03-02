from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import transaction
from django.db.models import Exists, F, OuterRef, QuerySet
from django.utils import timezone

from apps.users.models import User

from . import events
from .models import (
    Attachment,
    Conversation,
    ConversationParticipant,
    Delegation,
    Message,
    MessageType,
    ParticipantSide,
    ReadState,
)


def _create_system_message(conversation: Conversation, sender: User, content: str) -> Message:
    return Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=content,
        message_type=MessageType.SYSTEM_EVENT,
    )


def create_conversation(
    creator: User,
    participant_data: list[dict[str, Any]],
    subject: str = "",
    conversation_type: str = "general",
    property_id: UUID | None = None,
) -> Conversation:
    with transaction.atomic():
        conv = Conversation.objects.create(
            subject=subject,
            conversation_type=conversation_type,
            property_id=property_id,
        )

        participants = ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(
                    conversation=conv,
                    user_id=p["user_id"],
                    role=p["role"],
                    side=p["side"],
                )
                for p in participant_data
            ]
        )

        ReadState.objects.bulk_create(
            [ReadState(conversation=conv, user_id=p.user_id) for p in participants]
        )

        return conv


def send_message(
    sender: User,
    conversation: Conversation,
    content: str,
    message_type: str = "message",
    is_internal: bool = False,
) -> Message:
    with transaction.atomic():
        msg = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            message_type=message_type,
            is_internal=is_internal,
        )

        Conversation.objects.filter(id=conversation.id).update(updated_at=timezone.now())

        read_state_qs = ReadState.objects.filter(
            conversation=conversation,
        ).exclude(user=sender)

        # Pre-compute landlord IDs so the same list is reused for both
        # ReadState filtering and event broadcasting (avoids duplicate query).
        landlord_user_ids: list[Any] | None = None
        if is_internal:
            landlord_user_ids = list(
                ConversationParticipant.objects.filter(
                    conversation=conversation,
                    side=ParticipantSide.LANDLORD_SIDE,
                    is_active=True,
                )
                .exclude(user=sender)
                .values_list("user_id", flat=True)
            )
            read_state_qs = read_state_qs.filter(user_id__in=landlord_user_ids)

        read_state_qs.update(unread_count=F("unread_count") + 1)

        broadcast_ids = landlord_user_ids
        transaction.on_commit(
            lambda: events.broadcast_new_message(msg, landlord_user_ids=broadcast_ids)
        )

        return msg


def add_participant(
    conversation: Conversation,
    user: User,
    role: str,
    side: str,
    added_by: User,
) -> ConversationParticipant:
    with transaction.atomic():
        participant = ConversationParticipant.objects.create(
            conversation=conversation,
            user=user,
            role=role,
            side=side,
        )

        ReadState.objects.get_or_create(
            conversation=conversation,
            user=user,
        )

        _create_system_message(
            conversation,
            added_by,
            f"{user.first_name} {user.last_name} ble lagt til i samtalen.",
        )

        transaction.on_commit(
            lambda: events.broadcast_participant_change(conversation, user, "added")
        )

        return participant


def remove_participant(
    conversation: Conversation,
    user: User,
    removed_by: User,
) -> None:
    with transaction.atomic():
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=user,
            is_active=True,
        )
        participant.is_active = False
        participant.left_at = timezone.now()
        participant.save()

        _create_system_message(
            conversation,
            removed_by,
            f"{user.first_name} {user.last_name} ble fjernet fra samtalen.",
        )

        transaction.on_commit(
            lambda: events.broadcast_participant_change(conversation, user, "removed")
        )


def mark_as_read(
    user: User,
    conversation: Conversation,
    last_read_message_id: UUID,
) -> ReadState:
    with transaction.atomic():
        message = Message.objects.get(id=last_read_message_id, conversation=conversation)
        read_state, _ = ReadState.objects.get_or_create(
            conversation=conversation,
            user=user,
        )
        read_state.last_read_at = message.created_at
        read_state.last_read_message = message
        read_state.unread_count = 0
        read_state.save()

        transaction.on_commit(lambda: events.broadcast_read_update(user, conversation, 0))

    return read_state


def delegate_conversation(
    conversation: Conversation,
    assigned_to: User,
    assigned_by: User,
    note: str = "",
) -> Delegation:
    with transaction.atomic():
        Delegation.objects.filter(
            conversation=conversation,
            is_active=True,
        ).update(is_active=False)

        delegation = Delegation.objects.create(
            conversation=conversation,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            note=note,
        )

        _create_system_message(
            conversation,
            assigned_by,
            f"Samtalen ble delegert til {assigned_to.first_name} {assigned_to.last_name}.",
        )

        transaction.on_commit(
            lambda: events.broadcast_delegation_change(conversation, delegation, "assigned")
        )

        return delegation


def remove_delegation(
    conversation: Conversation,
    removed_by: User,
) -> None:
    with transaction.atomic():
        Delegation.objects.filter(
            conversation=conversation,
            is_active=True,
        ).update(is_active=False)

        _create_system_message(conversation, removed_by, "Delegering ble fjernet.")

        transaction.on_commit(
            lambda: events.broadcast_delegation_change(conversation, None, "removed")
        )


def search_messages(
    user: User,
    query: str | None = None,
    filters: dict[str, Any] | None = None,
) -> QuerySet[Message]:
    filters = filters or {}

    # Single base queryset for participant lookups (avoids duplicate queries)
    participant_qs = ConversationParticipant.objects.filter(user=user, is_active=True)
    user_conv_ids = participant_qs.values_list("conversation_id", flat=True)
    tenant_conv_ids = participant_qs.filter(side=ParticipantSide.TENANT_SIDE).values_list(
        "conversation_id", flat=True
    )

    qs = (
        Message.objects.filter(conversation_id__in=user_conv_ids)
        .exclude(conversation_id__in=tenant_conv_ids, is_internal=True)
        .select_related("sender", "conversation")
    )

    if query:
        search_query = SearchQuery(query, config="norwegian")
        qs = qs.filter(search_vector=search_query)
        qs = qs.annotate(rank=SearchRank(F("search_vector"), search_query))
        qs = qs.order_by("-rank")

    if "property" in filters:
        qs = qs.filter(conversation__property_id=filters["property"])

    if "status" in filters:
        qs = qs.filter(conversation__status=filters["status"])

    if "conversation_type" in filters:
        qs = qs.filter(conversation__conversation_type=filters["conversation_type"])

    if filters.get("has_attachment"):
        qs = qs.filter(Exists(Attachment.objects.filter(message=OuterRef("pk"))))

    if "date_from" in filters:
        qs = qs.filter(created_at__gte=filters["date_from"])

    if "date_to" in filters:
        qs = qs.filter(created_at__lte=filters["date_to"])

    if filters.get("unread_only"):
        unread_conv_ids = ReadState.objects.filter(user=user, unread_count__gt=0).values_list(
            "conversation_id", flat=True
        )
        qs = qs.filter(conversation_id__in=unread_conv_ids)

    return qs
