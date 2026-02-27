from __future__ import annotations

import os
from typing import Any, cast

from django.contrib.postgres.search import SearchHeadline, SearchQuery
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
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
    Message,
    MessageType,
    ReadState,
)
from .permissions import (
    IsConversationParticipant,
    get_participant_or_deny,
    get_user_conversations,
    get_visible_messages,
    require_landlord_side,
)
from .serializers import (
    AddParticipantSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    CreateConversationSerializer,
    CreateMessageSerializer,
    DelegateSerializer,
    MarkReadSerializer,
    MessageSearchResultSerializer,
    MessageSerializer,
    UpdateConversationSerializer,
)


def _user(request: Request) -> User:
    return cast(User, request.user)


class ConversationViewSet(viewsets.ModelViewSet[Conversation]):
    permission_classes = [IsConversationParticipant]

    def get_queryset(self) -> Any:
        user = _user(self.request)
        qs = get_user_conversations(user).select_related("property")

        if self.action == "list":
            # Annotate unread_count from ReadState to avoid N+1
            unread_sq = ReadState.objects.filter(conversation=OuterRef("pk"), user=user).values(
                "unread_count"
            )[:1]
            qs = qs.annotate(
                annotated_unread=Coalesce(Subquery(unread_sq), Value(0))
            ).prefetch_related("participants__user", "read_states", "messages__sender")

        return qs

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
        require_landlord_side(
            _user(request), conversation, "Bare utleiersiden kan utføre denne handlingen."
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


class MessageViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet[Message]
):
    serializer_class = MessageSerializer

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
        get_participant_or_deny(_user(request), conversation)

        serializer = CreateMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_internal = serializer.validated_data.get("is_internal", False)
        if is_internal:
            require_landlord_side(
                _user(request), conversation, "Bare utleiersiden kan sende interne kommentarer."
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
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


class AttachmentUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request: Request, conv_id: str, msg_id: str) -> Response:
        conversation = get_object_or_404(Conversation, id=conv_id)
        get_participant_or_deny(_user(request), conversation)

        message = get_object_or_404(Message, id=msg_id, conversation=conversation)

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

        attachment = Attachment.objects.create(
            message=message,
            file=uploaded_file,
            filename=uploaded_file.name,
            file_type=uploaded_file.content_type or "application/octet-stream",
            file_size=uploaded_file.size,
        )

        return Response(
            {
                "id": str(attachment.id),
                "filename": attachment.filename,
                "file_type": attachment.file_type,
                "file_size": attachment.file_size,
            },
            status=status.HTTP_201_CREATED,
        )


class AttachmentDownloadView(APIView):
    def get(self, request: Request, pk: str) -> HttpResponse:
        attachment = get_object_or_404(
            Attachment.objects.select_related("message__conversation"), id=pk
        )
        message = attachment.message
        conversation = message.conversation

        get_participant_or_deny(_user(request), conversation)

        if message.is_internal:
            require_landlord_side(
                _user(request), conversation, "Du har ikke tilgang til dette vedlegget."
            )

        response = HttpResponse()
        response["X-Accel-Redirect"] = f"/protected-media/{attachment.file.name}"
        response["Content-Type"] = ""
        response["Content-Disposition"] = f'attachment; filename="{attachment.filename}"'
        return response


class MessageSearchView(APIView):
    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip() or None
        filters: dict[str, Any] = {}

        if request.query_params.get("property"):
            filters["property"] = request.query_params["property"]
        if request.query_params.get("status"):
            filters["status"] = request.query_params["status"]
        if request.query_params.get("conversation_type"):
            filters["conversation_type"] = request.query_params["conversation_type"]
        if request.query_params.get("has_attachment", "").lower() == "true":
            filters["has_attachment"] = True
        if request.query_params.get("date_from"):
            filters["date_from"] = request.query_params["date_from"]
        if request.query_params.get("date_to"):
            filters["date_to"] = request.query_params["date_to"]
        if request.query_params.get("unread_only", "").lower() == "true":
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
