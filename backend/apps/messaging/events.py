from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ConversationParticipant, Message, ParticipantSide

if TYPE_CHECKING:
    from apps.users.models import User

    from .models import Conversation, Delegation

logger = logging.getLogger(__name__)


def _send_to_group(group: str, event: dict[str, Any]) -> None:
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(group, event)
    except Exception:
        logger.exception("Failed to send event to group %s", group)


def _get_landlord_side_user_ids(conversation: Conversation) -> list[str]:
    return [
        str(uid)
        for uid in ConversationParticipant.objects.filter(
            conversation=conversation,
            side=ParticipantSide.LANDLORD_SIDE,
            is_active=True,
        ).values_list("user_id", flat=True)
    ]


EVENT_VERSION = 1


def broadcast_new_message(message: Message, landlord_user_ids: list[Any] | None = None) -> None:
    payload = {
        "version": EVENT_VERSION,
        "message_id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender_id": str(message.sender_id),
        "sender_first_name": message.sender.first_name,
        "sender_last_name": message.sender.last_name,
        "sender_email": message.sender.email,
        "content": message.content,
        "message_type": message.message_type,
        "is_internal": message.is_internal,
    }

    if message.is_internal:
        # Internal: only landlord-side participants (use pre-computed IDs when available)
        user_ids = (
            [str(uid) for uid in landlord_user_ids]
            if landlord_user_ids is not None
            else _get_landlord_side_user_ids(message.conversation)
        )
    else:
        # Regular: all active participants via per-user groups (avoids N conversation
        # group subscriptions per connect — each user subscribes to 1 group only)
        user_ids = [
            str(uid)
            for uid in ConversationParticipant.objects.filter(
                conversation=message.conversation,
                is_active=True,
            ).values_list("user_id", flat=True)
        ]

    event = {"type": "message.new", **payload}
    for user_id in user_ids:
        if str(user_id) != str(message.sender_id):
            _send_to_group(f"user_{user_id}", event)


def broadcast_read_update(user: User, conversation: Conversation, unread_count: int) -> None:
    _send_to_group(
        f"user_{user.id}",
        {
            "type": "read.updated",
            "version": EVENT_VERSION,
            "conversation_id": str(conversation.id),
            "unread_count": unread_count,
        },
    )


def broadcast_participant_change(conversation: Conversation, user: User, action: str) -> None:
    event = {
        "type": f"participant.{action}",
        "version": EVENT_VERSION,
        "conversation_id": str(conversation.id),
        "user_id": str(user.id),
        "user_name": f"{user.first_name} {user.last_name}",
    }
    # Broadcast via per-user groups to all active participants
    participant_user_ids = ConversationParticipant.objects.filter(
        conversation=conversation,
        is_active=True,
    ).values_list("user_id", flat=True)
    for uid in participant_user_ids:
        _send_to_group(f"user_{uid}", event)


def broadcast_delegation_change(
    conversation: Conversation,
    delegation: Delegation | None,
    action: str,
    landlord_user_ids: list[Any] | None = None,
) -> None:
    payload = {
        "type": f"delegation.{action}",
        "version": EVENT_VERSION,
        "conversation_id": str(conversation.id),
    }
    if delegation:
        payload["assigned_to_id"] = str(delegation.assigned_to_id)
        payload["assigned_by_id"] = str(delegation.assigned_by_id)

    # Use pre-computed IDs when available to avoid duplicate query
    user_ids = (
        [str(uid) for uid in landlord_user_ids]
        if landlord_user_ids is not None
        else _get_landlord_side_user_ids(conversation)
    )
    for user_id in user_ids:
        _send_to_group(f"user_{user_id}", payload)


def broadcast_typing(conversation: Conversation, user: User, started: bool) -> None:
    action = "started" if started else "stopped"
    event = {
        "type": f"typing.{action}",
        "version": EVENT_VERSION,
        "conversation_id": str(conversation.id),
        "user_id": str(user.id),
        "user_name": f"{user.first_name} {user.last_name}".strip(),
    }
    # Broadcast via per-user groups (excludes the sender in consumer)
    participant_user_ids = ConversationParticipant.objects.filter(
        conversation=conversation,
        is_active=True,
    ).values_list("user_id", flat=True)
    for uid in participant_user_ids:
        if str(uid) != str(user.id):
            _send_to_group(f"user_{uid}", event)
