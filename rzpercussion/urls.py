"""
File: urls.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-07
Description: URL configuration for the rzpercussion app.
"""

from django.urls import path
from .views import (
    PiecesListView,
    PieceDetailView,
)

urlpatterns = [
    path("", PiecesListView.as_view(), name="pieces-list"),
    path("<slug:slug>/", PieceDetailView.as_view(), name="piece-detail"),
]
