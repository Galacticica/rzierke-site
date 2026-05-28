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
from django import forms
from unfold.admin import ModelAdmin, TabularInline

from .models import AlterEgo, Character, Movie, Relationship, Team, TeamMembership, Earth


class OrderedChoiceAdminMixin:
	"""Keep relation selectors in a predictable story order."""

	character_ordering = ("movie_introduced__release_date", "phase_introduced", "name")
	movie_ordering = ("release_date", "title")
	earth_ordering = ("number",)
	no_first_appearance_label = "No first appearance"

	def _grouped_character_choices(self, queryset):
		grouped_choices = []
		current_group_label = None
		current_group_choices = []

		for character in queryset.select_related("movie_introduced"):
			movie = character.movie_introduced
			group_label = movie.title if movie else self.no_first_appearance_label
			if group_label != current_group_label:
				if current_group_label is not None:
					grouped_choices.append((current_group_label, current_group_choices))
				current_group_label = group_label
				current_group_choices = []
			current_group_choices.append((character.pk, str(character)))

		if current_group_label is not None:
			grouped_choices.append((current_group_label, current_group_choices))

		return grouped_choices

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		remote_model = getattr(db_field.remote_field, "model", None)
		if remote_model is Character:
			kwargs["queryset"] = Character.objects.order_by(*self.character_ordering)
		elif remote_model is Movie:
			kwargs["queryset"] = Movie.objects.order_by(*self.movie_ordering)
		elif remote_model is Earth:
			kwargs["queryset"] = Earth.objects.order_by(*self.earth_ordering)
		form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
		if remote_model is Character:
			form_field.choices = self._grouped_character_choices(form_field.queryset)
		return form_field

	def formfield_for_manytomany(self, db_field, request, **kwargs):
		remote_model = getattr(db_field.remote_field, "model", None)
		if remote_model is Character:
			kwargs["queryset"] = Character.objects.order_by(*self.character_ordering)
		elif remote_model is Movie:
			kwargs["queryset"] = Movie.objects.order_by(*self.movie_ordering)
		form_field = super().formfield_for_manytomany(db_field, request, **kwargs)
		if remote_model is Character:
			form_field.choices = self._grouped_character_choices(form_field.queryset)
		return form_field


class GroupedCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
	template_name = "connections/widgets/grouped_checkbox_select.html"


class SearchableMovieSelect(forms.Select):
	template_name = "connections/widgets/searchable_movie_select.html"

	class Media:
		css = {"all": ("connections/movie_search_select.css",)}
		js = ("connections/movie_search_select.js",)


class CharacterAdminForm(forms.ModelForm):
	movie_introduced = forms.ModelChoiceField(
		queryset=Movie.objects.order_by("release_date", "title"),
		required=False,
		widget=SearchableMovieSelect(),
		label="First appearance movie",
	)
	latest_appearance = forms.ModelChoiceField(
		queryset=Movie.objects.order_by("release_date", "title"),
		required=False,
		widget=SearchableMovieSelect(),
		label="Latest appearance movie",
	)
	movies = forms.ModelMultipleChoiceField(
		queryset=Movie.objects.order_by("release_date", "title"),
		required=False,
		widget=GroupedCheckboxSelectMultiple(attrs={"class": "character-movies-grouped-select"}),
		label="Movies",
		help_text="Select every movie this character appears in.",
	)

	class Meta:
		model = Character
		fields = (
			"name",
			"phase_introduced",
			"movie_introduced",
			"latest_appearance",
			"alignment",
			"status",
			"earth_number",
			"photo_path",
			"movies",
		)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance.pk:
			self.fields["movies"].initial = self.instance.movies.all()


class RelationshipAdminForm(forms.ModelForm):
	direction = forms.ChoiceField(
		choices=(
			("forward", "Character 1 -> Character 2"),
			("reverse", "Character 2 -> Character 1"),
		),
		initial="forward",
		help_text="Choose which character should be treated as the source for directional relationships.",
	)

	class Meta:
		model = Relationship
		fields = (
			"character1",
			"character2",
			"relationship_type",
			"directional",
			"direction",
			"notes",
		)

	def save(self, commit=True):
		relationship = super().save(commit=False)
		if self.cleaned_data.get("direction") == "reverse":
			relationship.character1, relationship.character2 = relationship.character2, relationship.character1
		if commit:
			relationship.save()
			self.save_m2m()
		return relationship


class AlterEgoInline(TabularInline):
	"""Editable alter egos on the Character admin page."""
	model = AlterEgo
	extra = 0


class TeamMembershipInline(TabularInline):
	"""Editable team memberships on the Character admin page."""
	model = TeamMembership
	extra = 0


@admin.register(Character)
class CharacterAdmin(OrderedChoiceAdminMixin, ModelAdmin):
	"""Admin configuration for Character."""
	form = CharacterAdminForm
	list_display = ("name", "phase_introduced", "alignment", "status")
	search_fields = ("name",)
	list_filter = ("alignment", "status", "phase_introduced")
	inlines = [AlterEgoInline, TeamMembershipInline]

	def save_related(self, request, form, formsets, change):
		super().save_related(request, form, formsets, change)
		form.instance.movies.set(form.cleaned_data.get("movies", []))


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
class MovieAdmin(OrderedChoiceAdminMixin, ModelAdmin):
	"""Admin configuration for Movie."""
	list_display = ("title", "release_date")
	search_fields = ("title",)

	def formfield_for_manytomany(self, db_field, request, **kwargs):
		form_field = super().formfield_for_manytomany(db_field, request, **kwargs)
		if db_field.name == "characters":
			form_field.widget = GroupedCheckboxSelectMultiple(
				attrs={
					"class": "movie-characters-grouped-select",
				}
			)
			form_field.widget.choices = form_field.choices
		return form_field


@admin.register(Relationship)
class RelationshipAdmin(OrderedChoiceAdminMixin, ModelAdmin):
	"""Admin configuration for Relationship."""
	form = RelationshipAdminForm
	list_display = ("character1", "character2", "relationship_type", "directional", "weight")
	list_filter = ("relationship_type", "directional")
	search_fields = ("character1__name", "character2__name", "notes")

	def _relationship_character_label(self, character):
		earth = character.earth_number.number if character.earth_number else None
		return f"{character.name} ({earth})" if earth else character.name

	def _relationship_character_choices(self, queryset):
		grouped_choices = {}

		for character in queryset.select_related("earth_number", "movie_introduced").prefetch_related("movies"):
			related_movies = list(character.movies.all())
			if character.movie_introduced and character.movie_introduced not in related_movies:
				related_movies.append(character.movie_introduced)

			if not related_movies:
				group = grouped_choices.setdefault(
					None,
					{
						"movie": None,
						"label": "No Movie Appearance",
						"choices": [],
					},
				)
				group["choices"].append((character.pk, self._relationship_character_label(character)))
				continue

			seen_movie_ids = set()
			for movie in sorted(related_movies, key=lambda item: (item.release_date, item.title)):
				if movie.pk in seen_movie_ids:
					continue
				seen_movie_ids.add(movie.pk)
				group = grouped_choices.setdefault(
					movie.pk,
					{
						"movie": movie,
						"label": movie.title,
						"choices": [],
					},
				)
				group["choices"].append((character.pk, self._relationship_character_label(character)))

		sorted_groups = sorted(
			grouped_choices.values(),
			key=lambda group: (
				group["movie"] is None,
				group["movie"].release_date if group["movie"] is not None else None,
				group["movie"].title if group["movie"] is not None else group["label"],
			),
		)
		return [(group["label"], group["choices"]) for group in sorted_groups]

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		remote_model = getattr(db_field.remote_field, "model", None)
		if remote_model is Character:
			kwargs["queryset"] = Character.objects.select_related("earth_number", "movie_introduced").prefetch_related("movies").order_by(
				"earth_number__number",
				"name",
			)
			form_field = super(OrderedChoiceAdminMixin, self).formfield_for_foreignkey(db_field, request, **kwargs)
			form_field.choices = self._relationship_character_choices(form_field.queryset)
			return form_field
		return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Earth)
class EarthAdmin(ModelAdmin):
	"""Admin configuration for Earth."""
	list_display = ("number",)
	search_fields = ("number",)
