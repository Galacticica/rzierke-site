"""
File: urls.py
Author: Reagan Zierke
Date: 2026-01-21
Description: URL configuration for the home app.
"""

from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='homepage'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('blog/', views.BlogView.as_view(), name='blog'),
    path('resources/', views.ResourcesView.as_view(), name='resources'),
]