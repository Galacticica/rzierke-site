from django.contrib import admin as django_admin
from django.test import TestCase

from ..admin import CharacterAdmin, CharacterAdminForm, RelationshipAdmin, RelationshipAdminForm, SearchableRelationshipCharacterSelect
from ..models import Character, Earth, Movie, Relationship
from ..views import _group_character_options


class ConnectionsAdminTests(TestCase):
	def _character(self, name):
		return Character.objects.create(name=name)

	def _movie(self, title, release_date):
		return Movie.objects.create(title=title, release_date=release_date)

	def test_character_admin_form_syncs_movie_membership(self):
		movie_one = self._movie("Movie One", "2024-01-01")
		movie_two = self._movie("Movie Two", "2025-01-01")
		character = self._character("Test Character")

		form = CharacterAdminForm(
			data={
				"name": character.name,
				"phase_introduced": "",
				"movie_introduced": "",
				"alignment": "",
				"status": "",
				"earth_number": "",
				"photo_path": "",
				"movies": [str(movie_one.id), str(movie_two.id)],
			},
			instance=character,
		)

		self.assertTrue(form.is_valid(), form.errors)
		form.save(commit=False)
		CharacterAdmin(Character, django_admin.site).save_related(None, form, [], False)

		self.assertEqual(list(character.movies.order_by("title").values_list("title", flat=True)), ["Movie One", "Movie Two"])

	def test_character_admin_movie_selects_are_chronological(self):
		later_movie = self._movie("Later Movie", "2025-01-01")
		earliest_movie = self._movie("Earliest Movie", "2023-01-01")
		middle_movie = self._movie("Middle Movie", "2024-01-01")

		form = CharacterAdminForm()

		self.assertEqual(
			list(form.fields["movie_introduced"].queryset.values_list("title", flat=True)),
			["Earliest Movie", "Middle Movie", "Later Movie"],
		)


	def test_character_admin_sorts_earth_choices_alphabetically(self):
		Earth.objects.create(number="Earth-838")
		Earth.objects.create(number="Earth-616")
		Earth.objects.create(number="Earth-1610")

		form_field = CharacterAdmin(Character, django_admin.site).formfield_for_foreignkey(
			Character._meta.get_field("earth_number"),
			None,
		)

		self.assertEqual(
			list(form_field.queryset.values_list("number", flat=True)),
			["Earth-1610", "Earth-616", "Earth-838"],
		)

	def test_group_character_options_includes_earth_display_name(self):
		earth = Earth.objects.create(number="Earth-616")
		movie = self._movie("Movie One", "2024-01-01")
		character = self._character("Test Character")
		character.earth_number = earth
		character.movie_introduced = movie
		character.save(update_fields=["earth_number", "movie_introduced"])

		grouped_options = _group_character_options(Character.objects.select_related("movie_introduced", "earth_number").order_by("name"))
		self.assertEqual(grouped_options[0]["characters"][0]["display_name"], "Test Character (Earth-616)")

	def test_relationship_admin_keeps_grouped_characters_and_adds_search(self):
		movie_one = self._movie("Movie One", "2024-01-01")
		movie_two = self._movie("Movie Two", "2025-01-01")
		earth = Earth.objects.create(number="Earth-616")
		character = self._character("Test Character")
		character.earth_number = earth
		character.save(update_fields=["earth_number"])
		movie_one.characters.add(character)
		movie_two.characters.add(character)

		form_field = RelationshipAdmin(Relationship, django_admin.site).formfield_for_foreignkey(
			Relationship._meta.get_field("character1"),
			None,
		)

		self.assertIsInstance(form_field.widget, SearchableRelationshipCharacterSelect)
		grouped_choices = {label: choices for label, choices in form_field.choices}
		self.assertIn("Movie One", grouped_choices)
		self.assertIn("Movie Two", grouped_choices)
		self.assertEqual(grouped_choices["Movie One"], [(character.id, "Test Character (Earth-616)")])
		self.assertEqual(grouped_choices["Movie Two"], [(character.id, "Test Character (Earth-616)")])

	def test_relationship_admin_form_can_reverse_direction(self):
		first = self._character("First")
		second = self._character("Second")

		form = RelationshipAdminForm(
			data={
				"character1": str(first.id),
				"character2": str(second.id),
				"relationship_type": "Ally",
				"directional": True,
				"notes": "",
				"direction": "reverse",
			}
		)

		self.assertTrue(form.is_valid(), form.errors)
		relationship = form.save(commit=False)

		self.assertEqual((relationship.character1_id, relationship.character2_id), (second.id, first.id))
		self.assertTrue(relationship.directional)
