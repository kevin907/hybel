from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .events import EVENT_VERSION, broadcast_typing
from .models import ConversationParticipant, ReadState

if TYPE_CHECKING:
    from apps.users.models import User


@dataclass(frozen=True)
class _ConversationRef:
    id: str


class InboxConsumer(AsyncJsonWebsocketConsumer):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.user: User | None = None
        self.conversation_groups: list[str] = []
        self.user_group: str = ""

    async def connect(self) -> None:
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        conversation_ids = await self._get_active_conversation_ids()
        for conv_id in conversation_ids:
            group = f"conversation_{conv_id}"
            self.conversation_groups.append(group)
            await self.channel_layer.group_add(group, self.channel_name)

        await self.accept()

        initial_state = await self._build_sync_state(conversation_ids)
        await self.send_json(
            {"type": "connection.sync", "version": EVENT_VERSION, **initial_state}
        )

    async def disconnect(self, code: int) -> None:
        if self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        for group in self.conversation_groups:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        event_type = content.get("type")
        conversation_id = content.get("conversation_id")

        if event_type in ("typing.start", "typing.stop") and conversation_id:
            group = f"conversation_{conversation_id}"
            if group not in self.conversation_groups:
                return
            await database_sync_to_async(broadcast_typing)(
                _ConversationRef(id=conversation_id),
                self.user,
                started=(event_type == "typing.start"),
            )

    async def message_new(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def read_updated(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def participant_added(self, event: dict[str, Any]) -> None:
        conv_id = event.get("conversation_id")
        if conv_id:
            group = f"conversation_{conv_id}"
            if group not in self.conversation_groups:
                self.conversation_groups.append(group)
                await self.channel_layer.group_add(group, self.channel_name)
        await self.send_json(event)

    async def participant_removed(self, event: dict[str, Any]) -> None:
        conv_id = event.get("conversation_id")
        user_id = event.get("user_id")
        if user_id and self.user and str(user_id) == str(self.user.id) and conv_id:
            group = f"conversation_{conv_id}"
            if group in self.conversation_groups:
                self.conversation_groups.remove(group)
                await self.channel_layer.group_discard(group, self.channel_name)
        await self.send_json(event)

    async def delegation_assigned(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def delegation_removed(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def typing_started(self, event: dict[str, Any]) -> None:
        if not self.user or event.get("user_id") != str(self.user.id):
            await self.send_json(event)

    async def typing_stopped(self, event: dict[str, Any]) -> None:
        if not self.user or event.get("user_id") != str(self.user.id):
            await self.send_json(event)

    @database_sync_to_async  # type: ignore[untyped-decorator]
    def _get_active_conversation_ids(self) -> list[str]:
        return [
            str(cid)
            for cid in ConversationParticipant.objects.filter(
                user=self.user, is_active=True
            ).values_list("conversation_id", flat=True)
        ]

    @database_sync_to_async  # type: ignore[untyped-decorator]
    def _build_sync_state(self, conversation_ids: list[str]) -> dict[str, Any]:
        unread_counts = {}
        for rs in ReadState.objects.filter(user=self.user, conversation_id__in=conversation_ids):
            unread_counts[str(rs.conversation_id)] = rs.unread_count

        return {
            "conversations": [str(cid) for cid in conversation_ids],
            "unread_counts": unread_counts,
        }
