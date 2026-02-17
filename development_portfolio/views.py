"""
File: views.py
Author: Reagan Zierke
Date: 2026-02-15
Description: Views for the development portfolio section of the website.
"""

from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView

from .models import Project, Resource, Skill
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
        base_qs = Project.objects.all().order_by("-date", "project_name")

        project_filter = ProjectFilter(request.GET, queryset=base_qs)
        projects = project_filter.qs

        context = {
            "projects": projects,
            "filter": project_filter,
            "q": request.GET.get("q", ""),
            "total_count": Project.objects.count(),
            "filtered_count": projects.count(),
        }

        if getattr(request, "htmx", False):
            return render(request, "development_portfolio/partials/project_results.html", context)

        return render(
            request,
            "development_portfolio/dev_project_list.html",
            context,
        )
    
class DevProjectDetailView(DetailView):
    model = Project
    template_name = "development_portfolio/project_detail.html"
    context_object_name = "project"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Project.objects.with_related()


class ResourcesView(View):
    """A view to display a list of resources related to development."""

    def get(self, request):
        resources = Resource.objects.all()
        context = {
            "resources": resources,
        }
        return render(request, "development_portfolio/resources.html", context)