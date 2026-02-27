import asyncio
import contextlib

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser

from config.asgi import application

from .conftest import (
    ConversationFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)


@database_sync_to_async
def make_user(**kwargs):
    return UserFactory(**kwargs)


@database_sync_to_async
def make_conversation_with_participants(tenant, landlord):
    conv = ConversationFactory()
    ParticipantFactory(conversation=conv, user=tenant, role="tenant", side="tenant_side")
    ParticipantFactory(conversation=conv, user=landlord, role="landlord", side="landlord_side")
    ReadStateFactory(conversation=conv, user=tenant, unread_count=2)
    ReadStateFactory(conversation=conv, user=landlord, unread_count=0)
    return conv


async def connect_user(user):
    communicator = WebsocketCommunicator(application, "/ws/inbox/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    sync_msg = await communicator.receive_json_from(timeout=3)
    assert sync_msg["type"] == "connection.sync"
    return communicator, sync_msg


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketConnection:
    async def test_authenticated_user_connects(self):
        user = await make_user(first_name="Test", last_name="User")
        communicator = WebsocketCommunicator(application, "/ws/inbox/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_anonymous_user_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/inbox/")
        communicator.scope["user"] = AnonymousUser()
        connected, _ = await communicator.connect()
        assert not connected

    async def test_connection_sync_delivers_initial_state(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        communicator, sync_msg = await connect_user(tenant)

        payload = sync_msg["payload"]
        assert str(conv.id) in payload["conversations"]
        assert payload["unread_counts"][str(conv.id)] == 2

        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageBroadcasting:
    async def test_regular_message_delivered_to_all_participants(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)
        landlord_ws, _ = await connect_user(landlord)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "message.new",
                "message_id": "test-123",
                "conversation_id": str(conv.id),
                "sender_id": str(landlord.id),
                "content": "Heisen er reparert.",
                "is_internal": False,
            },
        )

        tenant_msg = await tenant_ws.receive_json_from(timeout=3)
        assert tenant_msg["type"] == "message.new"

        landlord_msg = await landlord_ws.receive_json_from(timeout=3)
        assert landlord_msg["type"] == "message.new"

        await tenant_ws.disconnect()
        await landlord_ws.disconnect()

    async def test_internal_comment_not_sent_to_tenant(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)
        landlord_ws, _ = await connect_user(landlord)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"user_{landlord.id}",
            {
                "type": "message.new",
                "message_id": "internal-123",
                "content": "Intern: koster 5000kr",
                "is_internal": True,
            },
        )

        landlord_msg = await landlord_ws.receive_json_from(timeout=3)
        assert landlord_msg["is_internal"] is True

        with pytest.raises(asyncio.TimeoutError):
            await tenant_ws.receive_json_from(timeout=1)

        with contextlib.suppress(asyncio.CancelledError):
            await tenant_ws.disconnect()
        await landlord_ws.disconnect()

    async def test_message_includes_sender_and_content(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "message.new",
                "message_id": "msg-456",
                "conversation_id": str(conv.id),
                "sender_id": str(landlord.id),
                "content": "Nøklene er klare.",
                "is_internal": False,
            },
        )

        msg = await tenant_ws.receive_json_from(timeout=3)
        assert msg["sender_id"] == str(landlord.id)
        assert msg["content"] == "Nøklene er klare."
        assert msg["conversation_id"] == str(conv.id)

        await tenant_ws.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestTypingIndicators:
    async def test_typing_start_broadcast(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)
        landlord_ws, _ = await connect_user(landlord)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "typing.started",
                "conversation_id": str(conv.id),
                "user_id": str(tenant.id),
            },
        )

        landlord_msg = await landlord_ws.receive_json_from(timeout=3)
        assert landlord_msg["type"] == "typing.started"
        assert landlord_msg["user_id"] == str(tenant.id)

        await tenant_ws.disconnect()
        await landlord_ws.disconnect()

    async def test_typing_not_echoed_to_sender(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)
        landlord_ws, _ = await connect_user(landlord)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "typing.started",
                "conversation_id": str(conv.id),
                "user_id": str(tenant.id),
            },
        )

        landlord_msg = await landlord_ws.receive_json_from(timeout=3)
        assert landlord_msg["type"] == "typing.started"

        with pytest.raises(asyncio.TimeoutError):
            await tenant_ws.receive_json_from(timeout=1)

        with contextlib.suppress(asyncio.CancelledError):
            await tenant_ws.disconnect()
        await landlord_ws.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestReadStateEvents:
    async def test_read_update_sent_to_user(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"user_{tenant.id}",
            {
                "type": "read.updated",
                "conversation_id": str(conv.id),
                "unread_count": 0,
            },
        )

        msg = await tenant_ws.receive_json_from(timeout=3)
        assert msg["type"] == "read.updated"
        assert msg["unread_count"] == 0

        await tenant_ws.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestParticipantEvents:
    async def test_participant_added_event(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)

        channel_layer = get_channel_layer()
        new_user = await make_user(first_name="New", last_name="Person")
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "participant.added",
                "conversation_id": str(conv.id),
                "user_id": str(new_user.id),
                "user_name": "New Person",
            },
        )

        msg = await tenant_ws.receive_json_from(timeout=3)
        assert msg["type"] == "participant.added"
        assert msg["user_name"] == "New Person"

        await tenant_ws.disconnect()

    async def test_participant_removed_event(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        landlord_ws, _ = await connect_user(landlord)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "participant.removed",
                "conversation_id": str(conv.id),
                "user_id": str(tenant.id),
                "user_name": "Tenant A",
            },
        )

        msg = await landlord_ws.receive_json_from(timeout=3)
        assert msg["type"] == "participant.removed"

        await landlord_ws.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDelegationEvents:
    async def test_delegation_assigned_event(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "delegation.assigned",
                "conversation_id": str(conv.id),
                "assigned_to_id": str(landlord.id),
                "assigned_by_id": str(landlord.id),
            },
        )

        msg = await tenant_ws.receive_json_from(timeout=3)
        assert msg["type"] == "delegation.assigned"
        assert msg["assigned_to_id"] == str(landlord.id)

        await tenant_ws.disconnect()

    async def test_delegation_removed_event(self):
        tenant = await make_user(first_name="Tenant", last_name="A")
        landlord = await make_user(first_name="Landlord", last_name="B")
        conv = await make_conversation_with_participants(tenant, landlord)

        tenant_ws, _ = await connect_user(tenant)

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"conversation_{conv.id}",
            {
                "type": "delegation.removed",
                "conversation_id": str(conv.id),
            },
        )

        msg = await tenant_ws.receive_json_from(timeout=3)
        assert msg["type"] == "delegation.removed"

        await tenant_ws.disconnect()
