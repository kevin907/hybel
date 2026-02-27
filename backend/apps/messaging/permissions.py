from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.users.models import User

from .models import Conversation, ConversationParticipant, Message, ParticipantSide


def get_participant_or_deny(user: User, conversation: Conversation) -> ConversationParticipant:
    try:
        return ConversationParticipant.objects.get(
            user=user, conversation=conversation, is_active=True
        )
    except ConversationParticipant.DoesNotExist:
        raise PermissionDenied("Du har ikke tilgang til denne samtalen.") from None


def get_user_side(user: User, conversation: Conversation) -> str:
    participant = get_participant_or_deny(user, conversation)
    return participant.side


def require_landlord_side(user: User, conversation: Conversation, message: str) -> None:
    if get_user_side(user, conversation) != ParticipantSide.LANDLORD_SIDE:
        raise PermissionDenied(message)


def can_see_message(user: User, message: Message) -> bool:
    if not message.is_internal:
        return True
    return get_user_side(user, message.conversation) == ParticipantSide.LANDLORD_SIDE


def get_visible_messages(user: User, conversation: Conversation) -> QuerySet[Message]:
    get_participant_or_deny(user, conversation)
    return Message.objects.visible_to(user, conversation)


def get_user_conversations(user: User) -> QuerySet[Conversation]:
    conversation_ids = ConversationParticipant.objects.filter(
        user=user, is_active=True
    ).values_list("conversation_id", flat=True)
    return Conversation.objects.filter(id__in=conversation_ids)


class IsConversationParticipant(BasePermission):
    def has_object_permission(self, request: Request, view: APIView, obj: Conversation) -> bool:
        try:
            get_participant_or_deny(cast(User, request.user), obj)
            return True
        except PermissionDenied:
            return False
