"""
File: admin.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: Registration of custom User model in admin.
"""


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AccessRequest


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User admin with email displayed."""
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active", "private_lyrics", "private_performances")
    list_filter = ("is_staff", "is_active", "private_lyrics", "private_performances")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Access", {"fields": ("private_lyrics", "private_performances", "gpt_creator")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    """Admin interface for access requests."""
    list_display = ("email", "request_type", "created_at")
    list_filter = ("request_type", "created_at")
    search_fields = ("email",)
    readonly_fields = ("email", "request_type", "created_at")
    ordering = ("-created_at",)
