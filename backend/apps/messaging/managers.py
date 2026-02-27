from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from apps.users.models import User

    from .models import Conversation, Message  # noqa: F401


class MessageQuerySet(models.QuerySet["Message"]):
    def visible_to(self, user: User, conversation: Conversation | None = None) -> MessageQuerySet:
        """Filter messages to only those visible to the given user.

        If conversation is provided, scope to that conversation and exclude
        internal messages when the user is on the tenant side.

        If no conversation is provided, exclude internal messages from all
        conversations where the user is on the tenant side.
        """
        from .models import ConversationParticipant, ParticipantSide

        qs = self

        if conversation:
            qs = qs.filter(conversation=conversation)
            try:
                participant = ConversationParticipant.objects.get(
                    user=user, conversation=conversation, is_active=True
                )
            except ConversationParticipant.DoesNotExist:
                return qs.none()

            if participant.side == ParticipantSide.TENANT_SIDE:
                qs = qs.exclude(is_internal=True)
        else:
            tenant_conv_ids = ConversationParticipant.objects.filter(
                user=user,
                is_active=True,
                side=ParticipantSide.TENANT_SIDE,
            ).values_list("conversation_id", flat=True)
            qs = qs.exclude(conversation_id__in=tenant_conv_ids, is_internal=True)

        return qs


class MessageManager(models.Manager["Message"]):
    def get_queryset(self) -> MessageQuerySet:
        return MessageQuerySet(self.model, using=self._db)

    def visible_to(self, user: User, conversation: Conversation | None = None) -> MessageQuerySet:
        return self.get_queryset().visible_to(user, conversation)
