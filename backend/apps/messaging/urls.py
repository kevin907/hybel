from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"conversations", views.ConversationViewSet, basename="conversation")

urlpatterns = [
    path(
        "conversations/search/",
        views.MessageSearchView.as_view(),
        name="message-search",
    ),
    path("", include(router.urls)),
    path(
        "conversations/<uuid:conv_id>/messages/",
        views.MessageViewSet.as_view({"get": "list", "post": "create"}),
        name="conversation-messages",
    ),
    path(
        "conversations/<uuid:conv_id>/messages/<uuid:msg_id>/attachments/",
        views.AttachmentUploadView.as_view(),
        name="message-attachment-upload",
    ),
    path(
        "attachments/<uuid:pk>/download/",
        views.AttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
]
