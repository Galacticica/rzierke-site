"""
File: urls.py
Author: Reagan Zierke
Date: 2026-02-15
Description: URL configurations for the development portfolio section of the website.
"""

from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.DevHomeView.as_view(), name='dev-home'),
    path('projects', views.DevPortfolioListView.as_view(), name='dev-project-list'),
    path('projects/<slug:slug>/', views.DevProjectDetailView.as_view(), name='dev-project-detail'),
    path('resources/', views.ResourcesView.as_view(), name='dev-resources'),
    path('bot-graveyard/', views.BotGraveyardView.as_view(), name='dev-bot-graveyard'),
    path('strudel-editor/', views.StrudelView.as_view(), name='dev-strudel'),
]