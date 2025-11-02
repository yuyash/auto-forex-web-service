"""
URL configuration for accounts app.

This module defines URL patterns for authentication endpoints.
"""

from django.urls import path

from .views import UserLoginView, UserRegistrationView

app_name = "accounts"

urlpatterns = [
    path("auth/register", UserRegistrationView.as_view(), name="register"),
    path("auth/login", UserLoginView.as_view(), name="login"),
]
