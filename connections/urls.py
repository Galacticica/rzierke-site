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
]