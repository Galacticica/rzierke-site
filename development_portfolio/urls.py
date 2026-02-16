"""
File: urls.py
Author: Reagan Zierke
Date: 2026-02-15
Description: URL configurations for the development portfolio section of the website.
"""

from django.urls import path, include
from . import views

urlpatterns = [
    path('/projects', views.DevPortfolioListView.as_view(), name='dev_project_list'),
]