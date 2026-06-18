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
    path('strudel-projects/<int:project_id>/', views.StrudelProjectDetailView.as_view(), name='strudel-project-detail'),
    path('strudel-projects/save/', views.StrudelProjectSaveView.as_view(), name='strudel-project-save'),
    path('wheel/', views.WheelView.as_view(), name='dev-wheel'),
    path('wheels/load/', views.WheelLoadView.as_view(), name='wheel-load'),
    path('wheels/save/', views.WheelSaveView.as_view(), name='wheel-save'),
    path('wheels/delete/', views.WheelDeleteView.as_view(), name='wheel-delete'),
    path('wheel-items/<int:item_id>/delete/', views.WheelItemDeleteView.as_view(), name='wheel-item-delete'),
]
