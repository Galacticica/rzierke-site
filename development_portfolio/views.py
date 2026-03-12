"""
File: views.py
Author: Reagan Zierke
Date: 2026-02-15
Description: Views for the development portfolio section of the website.
"""

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import DetailView

from .models import Project, Resource, Skill, Bot, StrudelProject
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

class BotGraveyardView(View):
    """A view to display a list of retired bots."""

    def get(self, request):
        bots = Bot.objects.all()
        bots_with_styles = []
        for i, bot in enumerate(bots):
            style_num = (i % 8) + 1
            bots_with_styles.append({
                'bot': bot,
                'style': f'style-{style_num}'
            })
        context = {
            "bots_with_styles": bots_with_styles,
        }
        return render(request, "development_portfolio/botyard.html", context)
    
class StrudelView(View):
    """A view to display the Strudel project."""

    def get(self, request):
        projects = (
            StrudelProject.objects.select_related("user")
            .order_by("name", "id")
        )
        project_payload = [
            {
                "id": project.id,
                "name": project.name,
                "user_id": project.user_id,
            }
            for project in projects
        ]
        context = {
            "strudel_projects": project_payload,
        }
        return render(request, "development_portfolio/strudel.html", context)


class StrudelProjectDetailView(View):
    """Return Strudel project details for loading into the editor."""

    def get(self, request, project_id: int):
        project = StrudelProject.objects.select_related("user").filter(id=project_id).first()
        if not project:
            return JsonResponse({"error": "Project not found."}, status=404)

        can_edit = request.user.is_authenticated and project.user_id == request.user.id
        return JsonResponse(
            {
                "id": project.id,
                "name": project.name,
                "text": project.text,
                "user_id": project.user_id,
                "can_edit": can_edit,
            }
        )


class StrudelProjectSaveView(View):
    """Create or update a Strudel project for the logged-in user."""

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload."}, status=400)

        name = (payload.get("name") or "").strip()
        text = payload.get("text") or ""
        project_id = payload.get("id")

        if not name:
            return JsonResponse({"error": "Project name is required."}, status=400)

        if project_id:
            project = StrudelProject.objects.filter(id=project_id).first()
            if not project:
                return JsonResponse({"error": "Project not found."}, status=404)
            if project.user_id != request.user.id:
                return JsonResponse({"error": "You do not have permission to edit this project."}, status=403)
            project.name = name
            project.text = text
            project.save(update_fields=["name", "text"])
        else:
            project = StrudelProject.objects.create(
                name=name,
                text=text,
                user=request.user,
            )

        return JsonResponse(
            {
                "id": project.id,
                "name": project.name,
                "text": project.text,
                "user_id": project.user_id,
                "can_edit": True,
            }
        )
