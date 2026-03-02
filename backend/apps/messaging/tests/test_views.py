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
    ConversationFactory,
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
class TestConversationListQueryCount:
    """S2.1 — Verify conversation list endpoint is N+1 free."""

    def test_list_query_count_is_constant(
        self, landlord_client, landlord_user, db, django_assert_max_num_queries
    ):
        """Query count should not grow linearly with conversation count."""
        for _ in range(10):
            conv = ConversationFactory()
            ParticipantFactory(
                conversation=conv, user=landlord_user, role="landlord", side="landlord_side"
            )
            MessageFactory(conversation=conv, sender=landlord_user)
            ReadStateFactory(conversation=conv, user=landlord_user)

        # With N+1 fixed, query count should be bounded (not 10x conversations)
        with django_assert_max_num_queries(15):
            response = landlord_client.get("/api/conversations/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 10

    def test_last_message_excludes_internal_for_list(
        self, tenant_client, conversation_with_participants, landlord_user
    ):
        """Tenant should see last public message in list, not internal comment."""
        conv, _, _ = conversation_with_participants
        MessageFactory(conversation=conv, sender=landlord_user, content="Public msg")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Secret note")

        response = tenant_client.get("/api/conversations/")
        last_msg = response.data["results"][0]["last_message"]
        assert last_msg is not None
        assert last_msg["is_internal"] is False
        assert "Public" in last_msg["content"]


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

    def test_non_owner_cannot_upload_to_others_message(
        self, landlord_client, conversation_with_participants, tenant_user
    ):
        """S2.5 — Users can only attach files to their own messages."""
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        upload = SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf")
        response = landlord_client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/attachments/",
            {"file": upload},
            format="multipart",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_download_attachment_returns_file_content(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        """Downloaded file should contain actual content, not be 0 bytes."""
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)
        att = AttachmentFactory(message=msg, file_type="application/pdf")
        file_content = b"PDF file content here"
        att.file.save("testfile.pdf", BytesIO(file_content))

        response = tenant_client.get(f"/api/attachments/{att.id}/download/")
        assert response.status_code == status.HTTP_200_OK
        body = b"".join(response.streaming_content)  # type: ignore[union-attr]
        assert len(body) > 0
        assert body == file_content

    def test_download_attachment_has_correct_content_type(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        """Downloaded file should have the correct Content-Type header."""
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)
        att = AttachmentFactory(message=msg, file_type="application/pdf")
        att.file.save("invoice.pdf", BytesIO(b"fake pdf"))

        response = tenant_client.get(f"/api/attachments/{att.id}/download/")
        assert response.status_code == status.HTTP_200_OK
        assert "application/pdf" in response["Content-Type"]

    def test_download_attachment_has_content_disposition(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        """Downloaded file should have Content-Disposition: attachment header."""
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)
        att = AttachmentFactory(message=msg, filename="kvittering.pdf")
        att.file.save("kvittering.pdf", BytesIO(b"receipt"))

        response = tenant_client.get(f"/api/attachments/{att.id}/download/")
        assert response.status_code == status.HTTP_200_OK
        assert "attachment" in response["Content-Disposition"]
        assert "kvittering.pdf" in response["Content-Disposition"]

    def test_upload_and_download_roundtrip(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        """Upload a file and download it — content should match byte-for-byte."""
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)
        original_content = b"This is the original file content for roundtrip test."

        upload = SimpleUploadedFile("roundtrip.txt", original_content, content_type="text/plain")
        upload_response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/attachments/",
            {"file": upload},
            format="multipart",
        )
        assert upload_response.status_code == status.HTTP_201_CREATED
        att_id = upload_response.data["id"]

        download_response = tenant_client.get(f"/api/attachments/{att_id}/download/")
        assert download_response.status_code == status.HTTP_200_OK
        downloaded = b"".join(download_response.streaming_content)  # type: ignore[union-attr]
        assert downloaded == original_content

    def test_upload_response_includes_uploaded_at(
        self, tenant_client, conversation_with_participants, tenant_user
    ):
        """Upload response should include uploaded_at for frontend consistency."""
        conv, _, _ = conversation_with_participants
        msg = MessageFactory(conversation=conv, sender=tenant_user)

        upload = SimpleUploadedFile("doc.pdf", b"pdf content", content_type="application/pdf")
        response = tenant_client.post(
            f"/api/conversations/{conv.id}/messages/{msg.id}/attachments/",
            {"file": upload},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "uploaded_at" in response.data


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

    def test_invalid_uuid_for_property_returns_400(self, landlord_client):
        """S2.4 — Search endpoint validates query parameters."""
        response = landlord_client.get("/api/conversations/search/?property=not-a-uuid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_date_returns_400(self, landlord_client):
        response = landlord_client.get("/api/conversations/search/?date_from=not-a-date")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_status_returns_400(self, landlord_client):
        response = landlord_client.get("/api/conversations/search/?status=invalid_status")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMessageCursorPagination:
    """S2.3 — Messages use cursor pagination for stable ordering."""

    def test_messages_return_cursor_links(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        for _ in range(60):
            MessageFactory(conversation=conv, sender=landlord_user)

        response = landlord_client.get(f"/api/conversations/{conv.id}/messages/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 50
        # Cursor pagination uses cursor param, not page
        assert response.data["next"] is not None
        assert "cursor" in response.data["next"]
        assert "page" not in response.data["next"]
        # Cursor pagination does not include count
        assert "count" not in response.data

    def test_cursor_follows_to_remaining_messages(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        for _ in range(60):
            MessageFactory(conversation=conv, sender=landlord_user)

        page1 = landlord_client.get(f"/api/conversations/{conv.id}/messages/")
        assert len(page1.data["results"]) == 50
        assert page1.data["next"] is not None

        # Follow the cursor to get remaining messages
        page2 = landlord_client.get(page1.data["next"])
        assert page2.status_code == status.HTTP_200_OK
        assert len(page2.data["results"]) == 10
        assert page2.data["next"] is None

    def test_cursor_stable_under_new_inserts(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        """Fetching page 2 returns same messages even if new messages arrive."""
        conv, _, _ = conversation_with_participants
        for _ in range(60):
            MessageFactory(conversation=conv, sender=landlord_user)

        page1 = landlord_client.get(f"/api/conversations/{conv.id}/messages/")
        cursor_url = page1.data["next"]

        # Insert new message between pages
        MessageFactory(conversation=conv, sender=landlord_user, content="NEW_AFTER_CURSOR")

        page2 = landlord_client.get(cursor_url)
        # page2 should contain older messages, not the newly inserted one
        contents = [m["content"] for m in page2.data["results"]]
        assert "NEW_AFTER_CURSOR" not in contents


@pytest.mark.django_db
class TestMessagesSinceEndpoint:
    """S4.2 — Fetch messages created after a given message ID."""

    def test_returns_only_newer_messages(
        self, landlord_client, conversation_with_participants, landlord_user
    ):
        conv, _, _ = conversation_with_participants
        m1 = MessageFactory(conversation=conv, sender=landlord_user, content="First")
        m2 = MessageFactory(conversation=conv, sender=landlord_user, content="Second")
        m3 = MessageFactory(conversation=conv, sender=landlord_user, content="Third")

        response = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [m["id"] for m in response.data]
        assert str(m1.id) not in ids
        assert str(m2.id) in ids
        assert str(m3.id) in ids

    def test_respects_internal_visibility(
        self, tenant_client, conversation_with_participants, landlord_user, tenant_user
    ):
        conv, _, _ = conversation_with_participants
        m1 = MessageFactory(conversation=conv, sender=tenant_user, content="Public")
        InternalCommentFactory(conversation=conv, sender=landlord_user, content="Secret")
        MessageFactory(conversation=conv, sender=landlord_user, content="Public2")

        response = tenant_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id={m1.id}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert all(not m["is_internal"] for m in response.data)
        contents = [m["content"] for m in response.data]
        assert "Secret" not in contents
        assert "Public2" in contents

    def test_missing_since_id_returns_400(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = landlord_client.get(f"/api/conversations/{conv.id}/messages/since/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_since_id_returns_400(self, landlord_client, conversation_with_participants):
        conv, _, _ = conversation_with_participants
        response = landlord_client.get(
            f"/api/conversations/{conv.id}/messages/since/?since_id=not-a-uuid"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
