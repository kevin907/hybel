from __future__ import annotations

import os
from typing import Any, cast
from urllib.parse import quote

from django.conf import settings
from django.contrib.postgres.search import SearchHeadline, SearchQuery
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import OuterRef, Prefetch, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.users.models import User

from . import services
from .models import (
    Attachment,
    Conversation,
    ConversationParticipant,
    Delegation,
    Message,
    MessageType,
    ReadState,
)
from .permissions import (
    IsConversationParticipant,
    get_cached_participant,
    get_participant_or_deny,
    get_user_conversations,
    get_visible_messages,
    require_participant_landlord_side,
)
from .serializers import (
    AddParticipantSerializer,
    AttachmentSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    CreateConversationSerializer,
    CreateMessageSerializer,
    DelegateSerializer,
    MarkReadSerializer,
    MessageSearchResultSerializer,
    MessageSerializer,
    SearchQuerySerializer,
    UpdateConversationSerializer,
)


def _user(request: Request) -> User:
    return cast(User, request.user)


class ConversationCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-updated_at"


class ConversationViewSet(viewsets.ModelViewSet[Conversation]):
    permission_classes = [IsConversationParticipant]
    pagination_class = ConversationCursorPagination

    def get_queryset(self) -> Any:
        user = _user(self.request)
        qs = get_user_conversations(user).select_related("property")

        if self.action == "list":
            # Annotate unread_count from ReadState to avoid N+1
            unread_sq = ReadState.objects.filter(conversation=OuterRef("pk"), user=user).values(
                "unread_count"
            )[:1]

            # Annotate last public message ID (avoids N+1 per-conversation query)
            last_msg_sq = (
                Message.objects.filter(conversation=OuterRef("pk"), is_internal=False)
                .order_by("-created_at")
                .values("id")[:1]
            )

            qs = qs.annotate(
                annotated_unread=Coalesce(Subquery(unread_sq), Value(0)),
                annotated_last_message_id=Subquery(last_msg_sq),
            ).prefetch_related(
                Prefetch(
                    "participants",
                    queryset=ConversationParticipant.objects.filter(is_active=True).select_related(
                        "user"
                    ),
                    to_attr="active_participants",
                ),
            )
        else:
            qs = qs.prefetch_related(
                Prefetch(
                    "participants",
                    queryset=ConversationParticipant.objects.select_related("user"),
                ),
                Prefetch(
                    "delegations",
                    queryset=Delegation.objects.filter(is_active=True).select_related(
                        "assigned_to", "assigned_by"
                    ),
                    to_attr="active_delegations",
                ),
            )

        return qs

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else list(queryset)

        # Batch-fetch last messages for all conversations on this page
        msg_ids = [
            c.annotated_last_message_id
            for c in items
            if getattr(c, "annotated_last_message_id", None)
        ]
        last_messages = {}
        if msg_ids:
            msgs = Message.objects.filter(id__in=msg_ids).select_related("sender")
            last_messages = {msg.id: msg for msg in msgs}

        serializer = self.get_serializer(
            items,
            many=True,
            context={**self.get_serializer_context(), "last_messages": last_messages},
        )

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        if self.action == "list":
            return ConversationListSerializer
        if self.action == "create":
            return CreateConversationSerializer
        if self.action in ("update", "partial_update"):
            return UpdateConversationSerializer
        return ConversationDetailSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_user_ids = [p["user_id"] for p in serializer.validated_data["participants"]]
        if _user(request).id not in participant_user_ids:
            return Response(
                {"detail": "Du må inkludere deg selv som deltaker."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conv = services.create_conversation(
            creator=_user(request),
            participant_data=serializer.validated_data["participants"],
            subject=serializer.validated_data.get("subject", ""),
            conversation_type=serializer.validated_data.get("conversation_type", "general"),
            property_id=serializer.validated_data.get("property_id"),
        )

        initial_message = serializer.validated_data.get("initial_message", "")
        if initial_message:
            services.send_message(
                sender=_user(request),
                conversation=conv,
                content=initial_message,
            )

        # Re-fetch with prefetching to avoid N+1 in serializer
        conv = (
            Conversation.objects.prefetch_related(
                Prefetch(
                    "participants",
                    queryset=ConversationParticipant.objects.select_related("user"),
                ),
                Prefetch(
                    "delegations",
                    queryset=Delegation.objects.filter(is_active=True).select_related(
                        "assigned_to", "assigned_by"
                    ),
                    to_attr="active_delegations",
                ),
            )
            .select_related("property")
            .get(id=conv.id)
        )
        output = ConversationDetailSerializer(conv, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        serializer.save()

    def perform_destroy(self, instance: Any) -> None:
        instance.status = "archived"
        instance.save()

    def _validated_landlord_action(
        self,
        request: Request,
        serializer_class: type[BaseSerializer[Any]] | None = None,
    ) -> tuple[Conversation, dict[str, Any]]:
        """Common boilerplate for landlord-side actions."""
        conversation = self.get_object()
        participant = get_cached_participant(request, conversation)
        require_participant_landlord_side(
            participant, "Bare utleiersiden kan utføre denne handlingen."
        )
        data: dict[str, Any] = {}
        if serializer_class:
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
        return conversation, data

    @action(detail=True, methods=["post"], url_path="participants")
    def add_participant(self, request: Request, pk: str | None = None) -> Response:
        conversation, data = self._validated_landlord_action(request, AddParticipantSerializer)

        user = get_object_or_404(User, id=data["user_id"])
        participant = services.add_participant(
            conversation=conversation,
            user=user,
            role=data["role"],
            side=data["side"],
            added_by=_user(request),
        )

        return Response(
            {"id": str(participant.id), "user_id": str(user.id)},
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"participants/(?P<user_id>[^/.]+)",
    )
    def remove_participant(
        self, request: Request, pk: str | None = None, user_id: str | None = None
    ) -> Response:
        conversation, _ = self._validated_landlord_action(request)

        user = get_object_or_404(User, id=user_id)
        services.remove_participant(
            conversation=conversation,
            user=user,
            removed_by=_user(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request: Request, pk: str | None = None) -> Response:
        conversation = self.get_object()
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rs = services.mark_as_read(
            user=_user(request),
            conversation=conversation,
            last_read_message_id=serializer.validated_data["last_read_message_id"],
        )
        return Response({"unread_count": rs.unread_count})

    @action(detail=True, methods=["post"], url_path="delegate")
    def delegate(self, request: Request, pk: str | None = None) -> Response:
        conversation, data = self._validated_landlord_action(request, DelegateSerializer)

        assigned_to = get_object_or_404(User, id=data["assigned_to"])
        delegation = services.delegate_conversation(
            conversation=conversation,
            assigned_to=assigned_to,
            assigned_by=_user(request),
            note=data.get("note", ""),
        )
        return Response(
            {"id": str(delegation.id), "assigned_to": str(assigned_to.id)},
            status=status.HTTP_201_CREATED,
        )

    @delegate.mapping.delete
    def remove_delegate(self, request: Request, pk: str | None = None) -> Response:
        conversation, _ = self._validated_landlord_action(request)

        services.remove_delegation(
            conversation=conversation,
            removed_by=_user(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-created_at"
    cursor_query_param = "cursor"


class MessageViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet[Message]
):
    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination

    def get_conversation(self) -> Conversation:
        return get_object_or_404(Conversation, id=self.kwargs["conv_id"])

    def get_queryset(self) -> Any:
        conversation = self.get_conversation()
        return (
            get_visible_messages(_user(self.request), conversation)
            .select_related("sender")
            .prefetch_related("attachments")
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        conversation = self.get_conversation()
        participant = get_cached_participant(self.request, conversation)

        serializer = CreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_internal = serializer.validated_data.get("is_internal", False)
        if is_internal:
            require_participant_landlord_side(
                participant, "Bare utleiersiden kan sende interne kommentarer."
            )

        message_type = MessageType.INTERNAL_COMMENT if is_internal else MessageType.MESSAGE

        msg = services.send_message(
            sender=_user(request),
            conversation=conversation,
            content=serializer.validated_data["content"],
            message_type=message_type,
            is_internal=is_internal,
        )

        output = MessageSerializer(msg, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class MessagesSinceView(APIView):
    """Gap-fill endpoint: fetch messages created after a given message ID."""

    def get(self, request: Request, conv_id: str) -> Response:
        conversation = get_object_or_404(Conversation, id=conv_id)
        # No permission class caching on APIView
        get_participant_or_deny(_user(request), conversation)

        since_id = request.query_params.get("since_id")
        if not since_id:
            return Response(
                {"detail": "Parameteren 'since_id' er påkrevd."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            since_msg = Message.objects.get(id=since_id, conversation=conversation)
        except (Message.DoesNotExist, ValueError, DjangoValidationError):
            return Response(
                {"detail": "Ugyldig meldings-ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            get_visible_messages(_user(request), conversation)
            .filter(created_at__gt=since_msg.created_at)
            .select_related("sender")
            .prefetch_related("attachments")
            .order_by("created_at")
        )

        serializer = MessageSerializer(qs[:200], many=True)
        return Response(serializer.data)


ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "text/plain",
}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


def _detect_mime_type(uploaded_file: Any) -> str:
    """Detect MIME type from file content using magic bytes."""
    import magic

    header = uploaded_file.read(2048)
    uploaded_file.seek(0)
    return magic.from_buffer(header, mime=True)


def _sanitize_content_disposition(filename: str) -> str:
    """Build a safe Content-Disposition header value with RFC 5987 encoding."""
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace('"', "_")
    utf8_name = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"


class AttachmentUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request: Request, conv_id: str, msg_id: str) -> Response:
        conversation = get_object_or_404(Conversation, id=conv_id)
        get_participant_or_deny(_user(request), conversation)

        message = get_object_or_404(Message, id=msg_id, conversation=conversation)

        if message.sender != _user(request):
            return Response(
                {"detail": "Du kan bare laste opp vedlegg til dine egne meldinger."},
                status=status.HTTP_403_FORBIDDEN,
            )

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "Ingen fil lastet opp."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            return Response(
                {"detail": f"Filtypen '{ext}' er ikke tillatt."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded_file.size > MAX_UPLOAD_SIZE:
            return Response(
                {"detail": "Filen er for stor. Maks 20 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        detected_mime = _detect_mime_type(uploaded_file)
        if detected_mime not in ALLOWED_MIME_TYPES:
            return Response(
                {"detail": "Filinnholdet samsvarer ikke med en tillatt filtype."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attachment = Attachment.objects.create(
            message=message,
            file=uploaded_file,
            filename=uploaded_file.name,
            file_type=detected_mime,
            file_size=uploaded_file.size,
        )

        return Response(
            AttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )


class AttachmentDownloadView(APIView):
    def get(self, request: Request, pk: str) -> FileResponse | HttpResponse:
        attachment = get_object_or_404(
            Attachment.objects.select_related("message__conversation"), id=pk
        )
        message = attachment.message
        conversation = message.conversation

        participant = get_participant_or_deny(_user(request), conversation)

        if message.is_internal:
            require_participant_landlord_side(
                participant, "Du har ikke tilgang til dette vedlegget."
            )

        # When nginx is configured as reverse proxy, enable USE_ACCEL_REDIRECT
        # in settings to serve files via X-Accel-Redirect for better performance.
        if getattr(settings, "USE_ACCEL_REDIRECT", False):
            response = HttpResponse()
            response["X-Accel-Redirect"] = f"/protected-media/{attachment.file.name}"
            response["Content-Type"] = ""
            response["Content-Disposition"] = _sanitize_content_disposition(attachment.filename)
            return response

        return FileResponse(
            attachment.file.open("rb"),
            content_type=attachment.file_type or "application/octet-stream",
            as_attachment=True,
            filename=attachment.filename,
        )


class MessageSearchView(APIView):
    def get(self, request: Request) -> Response:
        params = SearchQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        validated = params.validated_data

        query = validated.get("q", "").strip() or None
        filters: dict[str, Any] = {}

        if "property" in validated:
            filters["property"] = validated["property"]
        if "status" in validated:
            filters["status"] = validated["status"]
        if "conversation_type" in validated:
            filters["conversation_type"] = validated["conversation_type"]
        if validated.get("has_attachment"):
            filters["has_attachment"] = True
        if "date_from" in validated:
            filters["date_from"] = validated["date_from"]
        if "date_to" in validated:
            filters["date_to"] = validated["date_to"]
        if validated.get("unread_only"):
            filters["unread_only"] = True

        qs = services.search_messages(
            user=_user(request),
            query=query,
            filters=filters,
        )

        if query:
            search_query = SearchQuery(query, config="norwegian")
            qs = qs.annotate(
                headline=SearchHeadline(
                    "content",
                    search_query,
                    config="norwegian",
                    start_sel="<b>",
                    stop_sel="</b>",
                    max_words=35,
                    min_words=15,
                )
            )

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)

        serializer = MessageSearchResultSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
