"""
File: urls.py
Author: Reagan Zierke
Date: 2026-01-21
Description: description
"""

from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='homepage'),
]