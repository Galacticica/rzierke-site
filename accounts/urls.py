"""
File: urls.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: The URL configurations for the accounts app.
"""


from django.urls import path
from .views import MyLoginView, MySignupView, MyLogoutView


urlpatterns = [
    path("login/", MyLoginView.as_view(), name="login_page"),
    path("signup/", MySignupView.as_view(), name="signup_page"),
    path("logout/", MyLogoutView.as_view(), name="logout_page"),
]
