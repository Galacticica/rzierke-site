"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-15
Description: The admin configurations for development portfolio models.
- Provides enhanced interfaces for managing projects, project images, and tools.
"""

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Project, ProjectImage, Tool, Skill


class ProjectImageInline(admin.StackedInline):
    """Register ProjectImage as inline in Project admin."""
    model = ProjectImage
    extra = 0
    fields = ("image_source", "image_alt_text")
    classes = ("collapse",)


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    """Register Tool model in admin with basic configurations."""
    search_fields = ("name",)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    """Register Skill model in admin with basic configurations."""
    list_display = ("name", "date_started")
    list_filter = ("date_started",)
    search_fields = ("name",)
    ordering = ("-date_started",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """
    Register Project model in admin with enhanced configurations.
    This includes inlines for project images, custom list displays,
    search fields, and optimized queryset.
    """
    list_display = ("project_name", "category", "event", "date", "public", "tools_list")
    list_filter = ("public", "category", "date")
    search_fields = ("project_name", "description", "event", "category", "tool_used__name")
    filter_horizontal = ("tool_used",)
    inlines = [ProjectImageInline]
    prepopulated_fields = {"slug": ("project_name",)}
    date_hierarchy = "date"

    @admin.display(description="Tools")
    def tools_list(self, obj):
        names = list(obj.tool_used.values_list("name", flat=True))
        return ", ".join(names) if names else "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("tool_used", "images")
