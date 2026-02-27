from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf_token_view, name="csrf-token"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.me_view, name="me"),
    path("users/search/", views.user_search_view, name="user-search"),
]
