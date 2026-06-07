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

from urllib.parse import urlencode

from django.contrib import admin, messages
from django import forms
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path
from django.conf import settings
from unfold.admin import ModelAdmin, TabularInline

from .models import AlterEgo, Character, Movie, Relationship, Team, TeamMembership, Earth, BulkAddConfig


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


class SearchableRelationshipCharacterSelect(forms.Select):
	template_name = "connections/widgets/searchable_relationship_character_select.html"

	class Media:
		css = {"all": ("connections/relationship_character_search_select.css",)}
		js = ("connections/relationship_character_search_select.js",)


class CharacterAdminForm(forms.ModelForm):
	movie_introduced = forms.ModelChoiceField(
		queryset=Movie.objects.order_by("release_date", "title"),
		required=False,
		widget=SearchableMovieSelect(),
		label="First appearance movie",
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

	def clean(self):
		cleaned_data = super().clean()
		character1 = cleaned_data.get("character1")
		character2 = cleaned_data.get("character2")
		if character1 and character2 and character1 == character2:
			raise forms.ValidationError("A character can't be related to themself.")
		return cleaned_data

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
	change_list_template = "connections/admin/relationship_change_list.html"
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
			form_field.widget = SearchableRelationshipCharacterSelect()
			form_field.widget.choices = form_field.choices
			return form_field
		return super().formfield_for_foreignkey(db_field, request, **kwargs)

	def _relationship_adjacency(self):
		"""Map each character to the characters it already has any relationship with.

		Relationships are treated as undirected here so a target is hidden from a
		source regardless of which side it was stored on.
		"""
		adjacency = {}
		for char1_id, char2_id in Relationship.objects.values_list("character1_id", "character2_id"):
			adjacency.setdefault(char1_id, set()).add(char2_id)
			adjacency.setdefault(char2_id, set()).add(char1_id)
		return {character_id: sorted(related) for character_id, related in adjacency.items()}

	def _movie_variant_data(self):
		"""Compute variant relationships used by the bulk picker's Variants section.

		A "variant" is a different character that shares a name or an alias with a
		given character (e.g. the same hero on another earth). Returns a tuple of
		(variant_adjacency, movie_members, variant_options):

		- variant_adjacency: {character_id: [variant_character_id, ...]} — the
		  variants of each character. Drives the target picker: once a source is
		  chosen, its variants are surfaced even when a movie filter hides them.
		- movie_members: {movie_title: [character_id, ...]} — used to avoid showing
		  a variant in the Variants section when it is already in the filtered movie.
		- variant_options: [(character_id, label), ...] — the de-duplicated union of
		  every character that is some character's variant, rendered once per picker.
		"""
		characters = list(
			Character.objects.select_related("earth_number", "movie_introduced")
			.prefetch_related("alter_egos", "movies")
		)

		# Identity tokens (name + aliases) per character, and a reverse index.
		tokens_by_character = {}
		characters_by_token = {}
		characters_by_id = {}
		for character in characters:
			characters_by_id[character.pk] = character
			tokens = set()
			if character.name:
				tokens.add(character.name.strip().lower())
			for alter_ego in character.alter_egos.all():
				if alter_ego.name:
					tokens.add(alter_ego.name.strip().lower())
			tokens_by_character[character.pk] = tokens
			for token in tokens:
				characters_by_token.setdefault(token, set()).add(character.pk)

		# Characters sharing any token with the given character (excluding itself).
		variant_adjacency = {}
		variant_union = set()
		for character in characters:
			related = set()
			for token in tokens_by_character[character.pk]:
				related |= characters_by_token.get(token, set())
			related.discard(character.pk)
			if related:
				variant_adjacency[character.pk] = sorted(related)
				variant_union |= related

		# Which characters belong to each movie (matching the picker's grouping).
		members_by_movie = {}
		for character in characters:
			titles = {movie.title for movie in character.movies.all()}
			if character.movie_introduced:
				titles.add(character.movie_introduced.title)
			for title in titles:
				members_by_movie.setdefault(title, set()).add(character.pk)
		movie_members = {title: sorted(members) for title, members in members_by_movie.items()}

		variant_options = [
			(pk, self._relationship_character_label(characters_by_id[pk]))
			for pk in sorted(
				variant_union,
				key=lambda pk: (
					characters_by_id[pk].earth_number.number if characters_by_id[pk].earth_number else "",
					characters_by_id[pk].name,
				),
			)
		]
		return variant_adjacency, movie_members, variant_options

	change_form_template = "connections/admin/relationship_change_form.html"

	def add_view(self, request, form_url="", extra_context=None):
		extra_context = extra_context or {}
		extra_context["relationship_adjacency"] = self._relationship_adjacency()
		return super().add_view(request, form_url, extra_context)

	def change_view(self, request, object_id, form_url="", extra_context=None):
		extra_context = extra_context or {}
		extra_context["relationship_adjacency"] = self._relationship_adjacency()
		return super().change_view(request, object_id, form_url, extra_context)

	def get_urls(self):
		urls = super().get_urls()
		custom_urls = [
			path(
				"bulk-add/",
				self.admin_site.admin_view(self.bulk_add_view),
				name="connections_relationship_bulk_add",
			),
		]
		return custom_urls + urls

	def bulk_add_view(self, request):
		queryset = (
			Character.objects.select_related("earth_number", "movie_introduced")
			.prefetch_related("movies")
			.order_by("earth_number__number", "name")
		)
		character_choices = self._relationship_character_choices(queryset)
		created_count = 0

		if request.method == "POST":
			source_id = request.POST.get("source_character", "").strip()
			if not source_id:
				messages.error(request, "Please select a source character.")
			else:
				try:
					source_character = Character.objects.get(pk=source_id)
				except Character.DoesNotExist:
					messages.error(request, "Selected source character does not exist.")
					source_character = None

				if source_character:
					row_indices = sorted({
						int(key.split("-")[1])
						for key in request.POST
						if key.startswith("rows-") and key.endswith("-character2") and key.split("-")[1].isdigit()
					})

					for idx in row_indices:
						char2_id = request.POST.get(f"rows-{idx}-character2", "").strip()
						rel_type = request.POST.get(f"rows-{idx}-relationship_type", "").strip()
						directional = bool(request.POST.get(f"rows-{idx}-directional"))
						direction = request.POST.get(f"rows-{idx}-direction", "forward")
						notes = request.POST.get(f"rows-{idx}-notes", "").strip()

						if not char2_id or not rel_type:
							continue

						try:
							char2 = Character.objects.get(pk=char2_id)
						except Character.DoesNotExist:
							messages.error(request, f"Row {idx + 1}: target character not found.")
							continue

						if char2.pk == source_character.pk:
							messages.error(request, f"Row {idx + 1}: a character can't be related to themself.")
							continue

						char1, char2_final = source_character, char2
						if directional and direction == "reverse":
							char1, char2_final = char2, source_character

						try:
							_, created = Relationship.objects.get_or_create(
								character1=char1,
								character2=char2_final,
								relationship_type=rel_type,
								defaults={"directional": directional, "notes": notes},
							)
							if created:
								created_count += 1
							else:
								messages.warning(
									request,
									f"Already exists: {char1.name} ↔ {char2_final.name} ({rel_type})",
								)
						except Exception as e:
							messages.error(request, f"Row {idx + 1}: {e}")

			if created_count:
				messages.success(request, f"Created {created_count} relationship(s).")
				if "_save" in request.POST:
					return HttpResponseRedirect("../")
				# Default ("Save and add another"): start a fresh bulk add form,
				# keeping the movie filter applied if one was selected.
				movie_filter = request.POST.get("movie", "").strip()
				if movie_filter:
					return HttpResponseRedirect(f"{request.path}?{urlencode({'movie': movie_filter})}")
				return HttpResponseRedirect(request.path)

		selected_movie = request.POST.get("movie", "") if request.method == "POST" else request.GET.get("movie", "")
		variant_adjacency, movie_members, variant_options = self._movie_variant_data()

		# {character_id: "alias1 alias2 ..."} so the picker can match on aliases,
		# the same way the public graph search does.
		character_aliases = {}
		for character_id, alias_name in AlterEgo.objects.values_list("character_id", "name"):
			if alias_name:
				character_aliases.setdefault(str(character_id), []).append(alias_name)
		character_aliases = {cid: " ".join(names) for cid, names in character_aliases.items()}

		# Determine initial rows: prefer DB config, fallback to settings/env default.
		initial_rows = int(getattr(settings, "CONNECTIONS_BULK_ADD_DEFAULT_ROWS", 15))
		try:
			cfg = BulkAddConfig.objects.first()
			if cfg and cfg.default_rows:
				initial_rows = int(cfg.default_rows)
		except Exception:
			# If migrations haven't been run or DB unavailable, fall back to settings.
			pass

		context = {
			**self.admin_site.each_context(request),
			"title": "Bulk Add Relationships",
			"character_choices": character_choices,
			"relationship_choices": Relationship.RELATIONSHIP_CHOICES,
			"relationship_adjacency": self._relationship_adjacency(),
			"movie_choices": Movie.objects.order_by("release_date", "title"),
			"selected_movie": selected_movie,
			"variant_adjacency": variant_adjacency,
			"movie_members": movie_members,
			"variant_options": variant_options,
			"character_aliases": character_aliases,
			"opts": self.model._meta,
			"initial_rows": initial_rows,
			"app_label": self.model._meta.app_label,
		}
		return TemplateResponse(request, "connections/admin/bulk_add_relationships.html", context)


@admin.register(Earth)
class EarthAdmin(ModelAdmin):
	"""Admin configuration for Earth."""
	list_display = ("number",)
	search_fields = ("number",)


@admin.register(BulkAddConfig)
class BulkAddConfigAdmin(ModelAdmin):
	list_display = ("default_rows",)

	def has_add_permission(self, request):
		# Only allow a single config instance
		return not BulkAddConfig.objects.exists()
