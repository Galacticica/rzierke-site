"""
File: page_urls.py
Author: Reagan Zierke
Description: Public HTML pages for the connections app, mounted at /mcu-relationships/.
             The JSON endpoints live in urls.py, which is mounted under /api/.
"""

from django.urls import path

from . import views

urlpatterns = [
	path("", views.graph_page_view, name="connections-graph"),
	path("watch-order/", views.watch_order_page_view, name="connections-watch-order"),
]
