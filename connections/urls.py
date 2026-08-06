"""
File: urls.py
Author: Reagan Zierke
Date: 2026-05-25
Description: Defines the URL patterns for the connections app.
"""

from django.urls import path
from . import views

urlpatterns = [
	path("graph/", views.graph_view, name="graph"),
	path("graph/filter/", views.graph_filter_view, name="graph-filter"),
	path("graph/path/", views.graph_path_view, name="graph-path"),
	path("graph/character/<int:character_id>/", views.graph_character_detail_view, name="graph-character-detail"),
	path("watch-order/watched/", views.watch_order_watched_view, name="watch-order-watched"),
	path("watch-order/watched/sync/", views.watch_order_sync_view, name="watch-order-sync"),
]