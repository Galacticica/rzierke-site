"""
File: admin.py
Project: rzierke-site
Created Date: 2026-05-25
Author: Reagan Zierke
Email: reaganzierke@gmail.com
-----
Last Modified: 2026-05-25
Modified By: Reagan Zierke
-----
Description: Admin registrations for the connections app.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import AlterEgo, Character, Movie, Relationship, Team, TeamMembership


class AlterEgoInline(TabularInline):
	"""Editable alter egos on the Character admin page."""
	model = AlterEgo
	extra = 0


class TeamMembershipInline(TabularInline):
	"""Editable team memberships on the Character admin page."""
	model = TeamMembership
	extra = 0


@admin.register(Character)
class CharacterAdmin(ModelAdmin):
	"""Admin configuration for Character."""
	list_display = ("name", "phase_introduced", "alignment", "status")
	search_fields = ("name",)
	list_filter = ("alignment", "status", "phase_introduced")
	inlines = [AlterEgoInline, TeamMembershipInline]


@admin.register(AlterEgo)
class AlterEgoAdmin(ModelAdmin):
	"""Admin configuration for AlterEgo."""
	list_display = ("name", "character")
	search_fields = ("name", "character__name")


@admin.register(Team)
class TeamAdmin(ModelAdmin):
	"""Admin configuration for Team."""
	list_display = ("name",)
	search_fields = ("name",)


@admin.register(TeamMembership)
class TeamMembershipAdmin(ModelAdmin):
	"""Admin configuration for TeamMembership."""
	list_display = ("character", "team", "is_current_member")
	list_filter = ("is_current_member", "team")
	search_fields = ("character__name", "team__name")


@admin.register(Movie)
class MovieAdmin(ModelAdmin):
	"""Admin configuration for Movie."""
	list_display = ("title", "release_date")
	search_fields = ("title",)
	filter_horizontal = ("characters",)


@admin.register(Relationship)
class RelationshipAdmin(ModelAdmin):
	"""Admin configuration for Relationship."""
	list_display = ("character1", "character2", "relationship_type", "directional", "weight")
	list_filter = ("relationship_type", "directional")
	search_fields = ("character1__name", "character2__name", "notes")
