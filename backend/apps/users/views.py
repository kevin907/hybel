from typing import cast

from django.contrib.auth import authenticate, login, logout
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import User
from .serializers import UserSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token_view(request: Request) -> Response:
    """Return a CSRF token and set the csrftoken cookie."""
    token = get_token(request)
    return Response({"csrfToken": token})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_view(request: Request) -> Response:
    """Authenticate with email + password, create a session."""
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response(
            {"detail": "E-post og passord er påkrevd."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response(
            {"detail": "Ugyldig e-post eller passord."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user)
    return Response(UserSerializer(user).data)


login_view.throttle_scope = "login"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request: Request) -> Response:
    """Destroy the session."""
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request: Request) -> Response:
    """Return the currently authenticated user."""
    user = cast(User, request.user)
    return Response(UserSerializer(user).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_search_view(request: Request) -> Response:
    """Search users by name or email for autocomplete."""
    query = request.query_params.get("q", "").strip()
    if len(query) < 2:
        return Response([])

    current_user = cast(User, request.user)
    users = (
        User.objects.annotate(full_name=Concat("first_name", Value(" "), "last_name"))
        .filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
        .exclude(id=current_user.id)
        .only("id", "email", "first_name", "last_name")[:10]
    )

    return Response(UserSerializer(users, many=True).data)
