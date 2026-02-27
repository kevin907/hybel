from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from apps.messaging.models import (
    Attachment,
    ConversationParticipant,
    Message,
    ReadState,
)

from .conftest import (
    AttachmentFactory,
    InternalCommentFactory,
    MessageFactory,
    ParticipantFactory,
    ReadStateFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestConversationListAPI:
    def test_list_returns_only_user_conversations(
        self, tenant_client, conversation_with_participants
    ):
        response = tenant_client.get("/api/conversations/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_list_excludes_inactive_participations(
        self, tenant_client, conversation_with_participants
    ):
        _conv, tenant_p, _ = conversation_with_participants
        tenant_p.is_active = False
        tenant_p.save()

        response = tenant_client.get("/api/conversations/")
        assert len(response.data["results"]) == 0

    def test_list_includes_unread_count(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=3)

        response = tenant_client.get("/api/conversations/")
        assert response.data["results"][0]["unread_count"] == 3


@pytest.mark.django_db
class TestMessageListAPI:
    def test_tenant_does_not_see_internal_comments(
        self, tenant_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user)
        InternalCommentFactory(conversation=conv, sender=landlord_user)

        response = tenant_client.get(f"/api/conversations/{conv.id}/messages/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["is_internal"] is False

    def test_landlord_sees_internal_comments(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user)
        InternalCommentFactory(conversation=conv, sender=landlord_user)

        response = landlord_client.get(f"/api/conversations/{conv.id}/messages/")
        assert len(response.data["results"]) == 2

    def test_non_participant_cannot_access_messages(self, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        outsider = UserFactory()
        client = APIClient()
        client.force_authenticate(user=outsider)

        response = client.get(f"/api/conversations/{conv.id}/messages/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_send_message(self, tenant_client, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Hei, heisen er ødelagt igjen."},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["sender"]["id"] == str(tenant_user.id)

    def test_tenant_cannot_send_internal_comment(
        self, tenant_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern merknad", "is_internal": True},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestParticipantAPI:
    def test_add_participant(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()
        response = landlord_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {
                "user_id": str(new_user.id),
                "role": "contractor",
                "side": "landlord_side",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_remove_participant_soft_deletes(
        self, landlord_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        response = landlord_client.delete(
            f"/api/conversations/{conv.id}/participants/{tenant_user.id}/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        p = ConversationParticipant.objects.get(conversation=conv, user=tenant_user)
        assert p.is_active is False
        assert p.left_at is not None


@pytest.mark.django_db
class TestDelegationAPI:
    def test_delegate_conversation(
        self, landlord_client, conversation_with_participants, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )
        response = landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_tenant_cannot_delegate(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestReadStateAPI:
    def test_mark_as_read(
        self, tenant_client, conversation_with_participants, tenant_user, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=landlord_user)
        ReadStateFactory(conversation=conv, user=tenant_user, unread_count=1)

        response = tenant_client.post(
            f"/api/conversations/{conv.id}/read/",
            {"last_read_message_id": str(msg.id)},
        )
        assert response.status_code == status.HTTP_200_OK

        rs = ReadState.objects.get(conversation=conv, user=tenant_user)
        assert rs.unread_count == 0


@pytest.mark.django_db
class TestConversationCreateAPI:
    def test_create_conversation_with_participants(
        self, landlord_client, landlord_user, tenant_user
    ):
        response = landlord_client.post(
            "/api/conversations/",
            {
                "subject": "Nøkkelbytte",
                "conversation_type": "general",
                "participants": [
                    {
                        "user_id": str(landlord_user.id),
                        "role": "landlord",
                        "side": "landlord_side",
                    },
                    {"user_id": str(tenant_user.id), "role": "tenant", "side": "tenant_side"},
                ],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["subject"] == "Nøkkelbytte"
        assert (
            ConversationParticipant.objects.filter(conversation_id=response.data["id"]).count()
            == 2
        )

    def test_create_conversation_with_initial_message(
        self, landlord_client, landlord_user, tenant_user
    ):
        response = landlord_client.post(
            "/api/conversations/",
            {
                "subject": "Vedlikehold",
                "participants": [
                    {
                        "user_id": str(landlord_user.id),
                        "role": "landlord",
                        "side": "landlord_side",
                    },
                    {"user_id": str(tenant_user.id), "role": "tenant", "side": "tenant_side"},
                ],
                "initial_message": "Hei, varmtvann er borte.",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        conv_id = response.data["id"]
        assert Message.objects.filter(conversation_id=conv_id).count() == 1

    def test_create_without_participants_fails(self, landlord_client):
        response = landlord_client.post(
            "/api/conversations/",
            {"subject": "Tom samtale", "participants": []},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestConversationDetailAPI:
    def test_get_conversation_detail(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = tenant_client.get(f"/api/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert "participants" in response.data
        assert "active_delegation" in response.data

    def test_non_participant_cannot_get_detail(self, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        outsider = UserFactory()
        client = APIClient()
        client.force_authenticate(user=outsider)
        response = client.get(f"/api/conversations/{conv.id}/")
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


@pytest.mark.django_db
class TestConversationUpdateAPI:
    def test_update_status(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = landlord_client.patch(
            f"/api/conversations/{conv.id}/",
            {"status": "closed"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        conv.refresh_from_db()
        assert conv.status == "closed"

    def test_archive_conversation(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = landlord_client.delete(f"/api/conversations/{conv.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        conv.refresh_from_db()
        assert conv.status == "archived"


@pytest.mark.django_db
class TestAttachmentAPI:
    def test_upload_attachment(self, tenant_client, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        upload = SimpleUploadedFile("kvittering.pdf", b"fakepdf", content_type="application/pdf")
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/attachments/",
            {"file": upload},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Attachment.objects.filter(message=msg).count() == 1

    def test_download_attachment(self, tenant_client, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)
        att = AttachmentFactory(message=msg)
        att.file.save("testfile.pdf", BytesIO(b"testcontent"))

        response = tenant_client.get(f"/api/attachments/{att.id}/download/")
        assert response.status_code == status.HTTP_200_OK

    def test_tenant_cannot_download_internal_attachment(
        self, tenant_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        comment = InternalCommentFactory(conversation=conv, sender=landlord_user)
        att = AttachmentFactory(message=comment)
        att.file.save("secret.pdf", BytesIO(b"internal"))

        response = tenant_client.get(f"/api/attachments/{att.id}/download/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_upload_without_file_returns_400(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/attachments/",
            {},
            format="multipart",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Ingen fil" in response.data["detail"]

    def test_non_participant_cannot_upload(self, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        outsider = UserFactory()
        msg = MessageFactory(conversation=conv, sender=outsider)
        client = APIClient()
        client.force_authenticate(user=outsider)

        upload = SimpleUploadedFile("file.pdf", b"data", content_type="application/pdf")
        response = client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/attachments/",
            {"file": upload},
            format="multipart",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestConversationCreateAPIEdgeCases:
    def test_create_without_self_fails(self, landlord_client, tenant_user):
        response = landlord_client.post(
            "/api/conversations/",
            {
                "subject": "Without self",
                "participants": [
                    {"user_id": str(tenant_user.id), "role": "tenant", "side": "tenant_side"},
                ],
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "deg selv" in response.data["detail"]


@pytest.mark.django_db
class TestDelegationAPIEdgeCases:
    def test_remove_delegate(
        self, landlord_client, conversation_with_participants, property_manager_user
    ):
        conv, _, _ = conversation_with_participants
        ParticipantFactory(
            conversation=conv,
            user=property_manager_user,
            role="property_manager",
            side="landlord_side",
        )
        # First delegate
        landlord_client.post(
            f"/api/conversations/{conv.id}/delegate/",
            {"assigned_to": str(property_manager_user.id)},
        )
        # Then remove
        response = landlord_client.delete(f"/api/conversations/{conv.id}/delegate/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_tenant_cannot_remove_delegate(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = tenant_client.delete(f"/api/conversations/{conv.id}/delegate/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestParticipantAPIEdgeCases:
    def test_tenant_cannot_add_participant(self, tenant_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        new_user = UserFactory()
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/participants/",
            {"user_id": str(new_user.id), "role": "contractor", "side": "landlord_side"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_cannot_remove_participant(
        self, tenant_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        response = tenant_client.delete(
            f"/api/conversations/{conv.id}/participants/{landlord_user.id}/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMessageListAPIEdgeCases:
    def test_landlord_sends_internal_comment(
        self, landlord_client, conversation_with_participants
    ):
        conv, _, _ = conversation_with_participants
        response = landlord_client.post(
            f"/api/conversations/{conv.id}/messages/",
            {"content": "Intern merknad", "is_internal": True},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_internal"] is True


@pytest.mark.django_db
class TestSearchAPIEdgeCases:
    def test_search_with_filters(
        self, landlord_client, conversation_with_participants, landlord_user, sample_property
    ):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Heisen er ødelagt")

        response = landlord_client.get(
            "/api/conversations/search/",
            {"property": str(sample_property.id), "status": "open"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_search_empty_query(self, tenant_client, conversation_with_participants, tenant_user):
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=tenant_user, content="Noe tekst")

        response = tenant_client.get("/api/conversations/search/")
        assert response.status_code == status.HTTP_200_OK
