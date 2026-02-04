"""
File: urls.py
Author: Reagan Zierke
Date: 2026-02-02
Description: Song URLS
"""

from django.urls import path
from .views import SongDetailView, SongListView, SongPPTXExportView, SongPrintPDFView, MinHomeView

urlpatterns = [
    path("", MinHomeView.as_view(), name="min-home"),
    path("songs/", SongListView.as_view(), name="song-list"),
    path("songs/<slug:slug>/", SongDetailView.as_view(), name="song-detail"),
    path("songs/<slug:slug>/export/pptx/", SongPPTXExportView.as_view(), name="song-export-pptx"),
    path("songs/<slug:slug>/export/handout.pdf", SongPrintPDFView.as_view(), name="song-export-handout-pdf"),
]