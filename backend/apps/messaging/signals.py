from __future__ import annotations

from typing import Any

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Message, MessageType


@receiver(pre_save, sender=Message)
def sync_internal_flag(sender: type[Message], instance: Message, **kwargs: Any) -> None:
    if instance.message_type == MessageType.INTERNAL_COMMENT:
        instance.is_internal = True
    elif instance.message_type == MessageType.MESSAGE:
        instance.is_internal = False
