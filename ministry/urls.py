"""
File: urls.py
Author: Reagan Zierke
Date: 2026-02-02
Description: URL configuration for the ministry app.
"""

from django.urls import path
from .views import (
    DevotionsView,
    MinHomeView,
    PlaylistsView,
    RandomVerseView,
    SongDetailView,
    SongListView,
    SongPPTXExportView,
    SongPrintPDFView,
    VersesView,
)

urlpatterns = [
    path("", MinHomeView.as_view(), name="min-home"),
    path("devotions/", DevotionsView.as_view(), name="devotions"),
    path("playlists/", PlaylistsView.as_view(), name="playlists"),
    path("verses/", VersesView.as_view(), name="verses"),
    path("verses/<slug:category_slug>/<slug:theme_slug>/random/", RandomVerseView.as_view(), name="verse-random"),
    path("songs/", SongListView.as_view(), name="song-list"),
    path("songs/<slug:slug>/", SongDetailView.as_view(), name="song-detail"),
    path("songs/<slug:slug>/export/pptx/", SongPPTXExportView.as_view(), name="song-export-pptx"),
    path("songs/<slug:slug>/export/handout.pdf", SongPrintPDFView.as_view(), name="song-export-handout-pdf"),
]