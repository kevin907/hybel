import pytest
from rest_framework import status

from .conftest import (
    AttachmentFactory,
    ConversationFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    UserFactory,
)


@pytest.fixture
def searchable_conversation(conversation_with_participants, tenant_user, landlord_user):
    conv, _, _ = conversation_with_participants
    messages = {
        "leak": MessageFactory(
            conversation=conv,
            sender=tenant_user,
            content="Det er en vannlekkasje på badet.",
        ),
        "reply": MessageFactory(
            conversation=conv,
            sender=landlord_user,
            content="Vi sender en rørlegger i morgen.",
        ),
        "internal": InternalCommentFactory(
            conversation=conv,
            sender=landlord_user,
            content="Rørlegger koster 5000kr, dekkes av forsikring.",
        ),
    }
    return conv, messages


@pytest.mark.django_db
class TestSearchAccessControl:
    def test_tenant_search_excludes_internal_comments(
        self, tenant_client, searchable_conversation
    ):
        response = tenant_client.get("/api/conversations/search/", {"q": "rørlegger"})
        assert response.status_code == status.HTTP_200_OK
        contents = [r["content"] for r in response.data["results"]]
        assert any("rørlegger" in c.lower() for c in contents)
        assert not any("forsikring" in c for c in contents)
        assert not any(r["is_internal"] for r in response.data["results"])

    def test_landlord_search_includes_internal_comments(
        self, landlord_client, searchable_conversation
    ):
        response = landlord_client.get("/api/conversations/search/", {"q": "rørlegger"})
        contents = [r["content"] for r in response.data["results"]]
        assert any("forsikring" in c for c in contents)

    def test_search_only_returns_own_conversations(self, tenant_client, searchable_conversation):
        other_conv = ConversationFactory()
        other_user = UserFactory()
        ParticipantFactory(
            conversation=other_conv,
            user=other_user,
            role="tenant",
            side="tenant_side",
        )
        MessageFactory(
            conversation=other_conv,
            sender=other_user,
            content="vannlekkasje i kjelleren",
        )

        response = tenant_client.get("/api/conversations/search/", {"q": "vannlekkasje"})
        _conv, _ = searchable_conversation
        conv_ids = {r["conversation_id"] for r in response.data["results"]}
        assert str(other_conv.id) not in conv_ids

    def test_inactive_participant_excluded_from_search(
        self, tenant_client, searchable_conversation
    ):
        conv, _ = searchable_conversation
        from apps.messaging.models import ConversationParticipant

        ConversationParticipant.objects.filter(conversation=conv, side="tenant_side").update(
            is_active=False
        )

        response = tenant_client.get("/api/conversations/search/", {"q": "vannlekkasje"})
        assert len(response.data["results"]) == 0


@pytest.mark.django_db
class TestFullTextSearch:
    def test_norwegian_text_search(self, tenant_client, searchable_conversation):
        response = tenant_client.get("/api/conversations/search/", {"q": "vannlekkasje"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_no_results_returns_empty(self, tenant_client, searchable_conversation):
        response = tenant_client.get("/api/conversations/search/", {"q": "umuligord123"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_empty_query_returns_all_accessible(self, tenant_client, searchable_conversation):
        response = tenant_client.get("/api/conversations/search/")
        assert response.status_code == status.HTTP_200_OK
        assert not any(r["is_internal"] for r in response.data["results"])
        assert len(response.data["results"]) >= 2

    def test_search_returns_conversation_context(self, tenant_client, searchable_conversation):
        response = tenant_client.get("/api/conversations/search/", {"q": "vannlekkasje"})
        result = response.data["results"][0]
        assert "conversation_id" in result
        assert "conversation_subject" in result


@pytest.mark.django_db
class TestSearchFilters:
    def test_filter_by_property(self, tenant_client, searchable_conversation, sample_property):
        response = tenant_client.get(
            "/api/conversations/search/",
            {"property": str(sample_property.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_filter_by_status(self, tenant_client, searchable_conversation):
        response = tenant_client.get("/api/conversations/search/", {"status": "open"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_filter_by_status_closed_returns_empty(self, tenant_client, searchable_conversation):
        response = tenant_client.get("/api/conversations/search/", {"status": "closed"})
        assert len(response.data["results"]) == 0

    def test_filter_by_conversation_type(self, tenant_client, searchable_conversation):
        conv, _ = searchable_conversation
        conv.conversation_type = "maintenance"
        conv.save()

        response = tenant_client.get(
            "/api/conversations/search/", {"conversation_type": "maintenance"}
        )
        assert len(response.data["results"]) >= 1

    def test_filter_by_has_attachment(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user, content="Se vedlegg")
        AttachmentFactory(message=msg)

        response = tenant_client.get("/api/conversations/search/", {"has_attachment": "true"})
        assert response.status_code == status.HTTP_200_OK
        result_ids = [r["id"] for r in response.data["results"]]
        assert str(msg.id) in result_ids

    def test_filter_by_date_range(self, tenant_client, searchable_conversation):
        from django.utils import timezone

        now = timezone.now()
        response = tenant_client.get(
            "/api/conversations/search/",
            {
                "date_from": (now - timezone.timedelta(hours=1)).isoformat(),
                "date_to": (now + timezone.timedelta(hours=1)).isoformat(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_combined_filters(self, tenant_client, searchable_conversation, sample_property):
        response = tenant_client.get(
            "/api/conversations/search/",
            {
                "q": "vannlekkasje",
                "property": str(sample_property.id),
                "status": "open",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_filter_by_unread_only(self, tenant_client, searchable_conversation, tenant_user):
        conv, _ = searchable_conversation
        from apps.messaging.models import ReadState

        ReadState.objects.update_or_create(
            conversation=conv,
            user=tenant_user,
            defaults={"unread_count": 3},
        )

        response = tenant_client.get("/api/conversations/search/", {"unread_only": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1
