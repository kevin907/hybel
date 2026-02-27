import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from .managers import MessageManager


class ConversationType(models.TextChoices):
    GENERAL = "general", "General"
    MAINTENANCE = "maintenance", "Maintenance"
    LEASE = "lease", "Lease"
    RENT_QUERY = "rent_query", "Rent Query"


class ConversationStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"
    ARCHIVED = "archived", "Archived"


class ParticipantRole(models.TextChoices):
    TENANT = "tenant", "Tenant"
    LANDLORD = "landlord", "Landlord"
    PROPERTY_MANAGER = "property_manager", "Property Manager"
    CONTRACTOR = "contractor", "Contractor"
    STAFF = "staff", "Staff"


class ParticipantSide(models.TextChoices):
    TENANT_SIDE = "tenant_side", "Tenant Side"
    LANDLORD_SIDE = "landlord_side", "Landlord Side"


class MessageType(models.TextChoices):
    MESSAGE = "message", "Message"
    INTERNAL_COMMENT = "internal_comment", "Internal Comment"
    SYSTEM_EVENT = "system_event", "System Event"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        related_name="conversations",
        blank=True,
        null=True,
    )
    subject = models.CharField(max_length=255, blank=True)
    conversation_type = models.CharField(
        max_length=20,
        choices=ConversationType.choices,
        default=ConversationType.GENERAL,
    )
    status = models.CharField(
        max_length=20,
        choices=ConversationStatus.choices,
        default=ConversationStatus.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["-updated_at"], name="idx_conv_updated"),
            models.Index(fields=["status"], name="idx_conv_status"),
            models.Index(fields=["property"], name="idx_conv_property"),
        ]

    def __str__(self) -> str:
        return self.subject or f"Conversation {self.id}"


class ConversationParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participations",
    )
    role = models.CharField(max_length=20, choices=ParticipantRole.choices)
    side = models.CharField(max_length=20, choices=ParticipantSide.choices)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["conversation", "user"], name="idx_participant_conv_user"),
            models.Index(fields=["user", "is_active"], name="idx_participant_user_active"),
            models.Index(fields=["side"], name="idx_participant_side"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_participant",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.conversation} ({self.role})"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.MESSAGE,
    )
    is_internal = models.BooleanField(default=False)
    search_vector = SearchVectorField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MessageManager()

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="idx_msg_conv_created"),
            models.Index(fields=["is_internal"], name="idx_msg_internal"),
            GinIndex(fields=["search_vector"], name="idx_msg_search"),
        ]

    def __str__(self) -> str:
        return f"Message by {self.sender} in {self.conversation}"


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="attachments/%Y/%m/")
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.filename


class ReadState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="read_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="read_states",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_read_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_read_state",
            ),
        ]

    def __str__(self) -> str:
        return f"ReadState for {self.user} in {self.conversation}"


class Delegation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="delegations",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delegated_conversations",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delegations_made",
    )
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Delegation to {self.assigned_to} for {self.conversation}"
