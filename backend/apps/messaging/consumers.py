from __future__ import annotations

import asyncio
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
        self.user_group: str = ""
        self._active_conversation_ids: set[str] = set()
        self._ping_task: asyncio.Task[None] | None = None
        self._last_typing_broadcast: float = 0

    async def connect(self) -> None:
        self.user = self.scope.get("user")
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        self.user_group = f"user_{self.user.id}"

        # Single group subscription — all events routed via per-user groups
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        await self.accept()

        conversation_ids = await self._get_active_conversation_ids()
        self._active_conversation_ids = set(conversation_ids)

        initial_state = await self._build_sync_state(conversation_ids)
        await self.send_json(
            {"type": "connection.sync", "version": EVENT_VERSION, **initial_state}
        )

        # Start ping/pong keep-alive loop
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def disconnect(self, code: int) -> None:
        # Cancel ping task
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

        if self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        event_type = content.get("type")
        conversation_id = content.get("conversation_id")

        if event_type == "pong":
            return  # Client responded to ping — connection is alive

        if event_type in ("typing.start", "typing.stop") and conversation_id:
            if conversation_id not in self._active_conversation_ids:
                return

            # Server-side typing throttle: max 1 typing.start per 2 seconds
            if event_type == "typing.start":
                now = asyncio.get_event_loop().time()
                if (now - self._last_typing_broadcast) < 2.0:
                    return
                self._last_typing_broadcast = now

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
            self._active_conversation_ids.add(conv_id)
        await self.send_json(event)

    async def participant_removed(self, event: dict[str, Any]) -> None:
        conv_id = event.get("conversation_id")
        user_id = event.get("user_id")
        if user_id and self.user and str(user_id) == str(self.user.id) and conv_id:
            self._active_conversation_ids.discard(conv_id)
        await self.send_json(event)

    async def delegation_assigned(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def delegation_removed(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def typing_started(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def typing_stopped(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    async def _ping_loop(self) -> None:
        """Send periodic pings to detect dead connections."""
        try:
            while True:
                await asyncio.sleep(30)
                await self.send_json({"type": "ping"})
        except asyncio.CancelledError:
            pass

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
        # Use values_list to avoid full model instantiation
        unread_counts = dict(
            ReadState.objects.filter(
                user=self.user, conversation_id__in=conversation_ids
            ).values_list("conversation_id", "unread_count")
        )

        return {
            "conversations": conversation_ids,
            "unread_counts": {str(k): v for k, v in unread_counts.items()},
        }
