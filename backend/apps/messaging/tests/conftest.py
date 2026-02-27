import factory
import pytest
from factory.django import DjangoModelFactory
from rest_framework.test import APIClient

from apps.messaging.models import (
    Attachment,
    Conversation,
    ConversationParticipant,
    Delegation,
    Message,
    ReadState,
)
from apps.properties.models import Property
from apps.users.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@hybel.no")
    username = factory.LazyAttribute(lambda o: o.email)
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class PropertyFactory(DjangoModelFactory):
    class Meta:
        model = Property

    name = factory.Faker("street_address")


class ConversationFactory(DjangoModelFactory):
    class Meta:
        model = Conversation
        skip_postgeneration_save = True

    subject = factory.Faker("sentence", nb_words=4)
    conversation_type = "general"
    status = "open"

    @factory.post_generation
    def property(self, create, extracted, **kwargs):
        if extracted:
            self.property = extracted
            self.save()


class ParticipantFactory(DjangoModelFactory):
    class Meta:
        model = ConversationParticipant

    conversation = factory.SubFactory(ConversationFactory)
    user = factory.SubFactory(UserFactory)
    role = "tenant"
    side = "tenant_side"
    is_active = True


class MessageFactory(DjangoModelFactory):
    class Meta:
        model = Message

    conversation = factory.SubFactory(ConversationFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.Faker("paragraph")
    message_type = "message"
    is_internal = False


class InternalCommentFactory(MessageFactory):
    message_type = "internal_comment"
    is_internal = True
    content = factory.Faker("sentence")


class AttachmentFactory(DjangoModelFactory):
    class Meta:
        model = Attachment

    message = factory.SubFactory(MessageFactory)
    filename = "document.pdf"
    file_type = "application/pdf"
    file_size = 1024


class ReadStateFactory(DjangoModelFactory):
    class Meta:
        model = ReadState

    conversation = factory.SubFactory(ConversationFactory)
    user = factory.SubFactory(UserFactory)
    unread_count = 0


class DelegationFactory(DjangoModelFactory):
    class Meta:
        model = Delegation

    conversation = factory.SubFactory(ConversationFactory)
    assigned_to = factory.SubFactory(UserFactory)
    assigned_by = factory.SubFactory(UserFactory)
    is_active = True


@pytest.fixture
def tenant_user(db):
    return UserFactory(first_name="Tenant", last_name="Hansen")


@pytest.fixture
def landlord_user(db):
    return UserFactory(first_name="Landlord", last_name="Nilsen")


@pytest.fixture
def tenant_client(tenant_user):
    client = APIClient()
    client.force_authenticate(user=tenant_user)
    return client


@pytest.fixture
def landlord_client(landlord_user):
    client = APIClient()
    client.force_authenticate(user=landlord_user)
    return client


@pytest.fixture
def property_manager_user(db):
    return UserFactory(first_name="Manager", last_name="Berg")


@pytest.fixture
def contractor_user(db):
    return UserFactory(first_name="Contractor", last_name="Olsen")


@pytest.fixture
def sample_property(db):
    return PropertyFactory(name="Storgata 15, Oslo")


@pytest.fixture
def conversation_with_participants(db, tenant_user, landlord_user, sample_property):
    conv = ConversationFactory(property=sample_property)
    tenant_p = ParticipantFactory(
        conversation=conv,
        user=tenant_user,
        role="tenant",
        side="tenant_side",
    )
    landlord_p = ParticipantFactory(
        conversation=conv,
        user=landlord_user,
        role="landlord",
        side="landlord_side",
    )
    return conv, tenant_p, landlord_p


@pytest.fixture
def multi_participant_conversation(
    db,
    tenant_user,
    landlord_user,
    property_manager_user,
    contractor_user,
    sample_property,
):
    conv = ConversationFactory(property=sample_property, subject="Vannlekkasje")
    participants = {
        "tenant": ParticipantFactory(
            conversation=conv,
            user=tenant_user,
            role="tenant",
            side="tenant_side",
        ),
        "landlord": ParticipantFactory(
            conversation=conv,
            user=landlord_user,
            role="landlord",
            side="landlord_side",
        ),
        "manager": ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        ),
        "contractor": ParticipantFactory(
            conversation=conv,
            user=contractor_user,
            role="contractor",
            side="landlord_side",
        ),
    }
    return conv, participants
