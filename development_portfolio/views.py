"""
File: views.py
Author: Reagan Zierke
Date: 2026-02-15
Description: Views for the development portfolio section of the website.
"""

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import DetailView
from django.http import HttpResponse

from .models import Project, Skill
from .filters import ProjectFilter


class DevHomeView(View):
    """The home view for the development portfolio section, showing an overview of projects."""

    def get(self, request):
        skills = Skill.objects.all()
        context = {
            'skills': skills,
        }
        return render(
            request,
            "development_portfolio/dev_main.html",
            context,
        )


class DevPortfolioListView(View):
    """The list view for the development portfolio section, showing a list of projects with filtering."""

    def get(self, request):
        base_qs = Project.objects.all().order_by("-date_started", "title")

        project_filter = ProjectFilter(request.GET, queryset=base_qs)
        projects = project_filter.qs

        context = {
            "projects": projects,
            "filter": project_filter,
            "q": request.GET.get("q", ""),
            "total_count": Project.objects.count(),
            "filtered_count": projects.count(),
        }

        return render(
            request,
            "development_portfolio/dev_project_list.html",
            context,
        )
    
