"""Forms for the connections admin.

The watch-order form exists to keep ordering painless: `insert_after` is not a
model field, it is a chooser that computes a sparse `position` so adding a film
between two others never renumbers its neighbours.
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import WatchEntry, append_position, next_position_after
from .poster_matching import find_poster
from .watch_order_service import would_create_cycle


class WatchEntryAdminForm(forms.ModelForm):
	"""Watch-order entry form with an "insert after" chooser instead of a raw position."""

	insert_after = forms.ModelChoiceField(
		queryset=WatchEntry.objects.select_related("track").order_by(
			"track__lane_order", "position", "pk"
		),
		required=False,
		label="Insert after",
		help_text="Drop this entry straight after another one. Leave blank to append to the "
		          "end of its track, or to keep the current position when editing.",
	)

	class Meta:
		model = WatchEntry
		fields = "__all__"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# Optional, not disabled: 'Insert after' is the convenient path, but a
		# position typed by hand has to win over any convenience.
		if "position" in self.fields:
			self.fields["position"].required = False
			self.fields["position"].help_text = (
				"Order within the track - lower comes first. Leave blank to append to the end, "
				"or use 'Insert after' to drop it between two entries. Decimals are fine "
				"(15 sits between 10 and 20). If both are set, 'Insert after' wins."
			)

		# An entry cannot be inserted after itself, nor be its own prerequisite.
		if self.instance.pk:
			for field_name in ("insert_after", "prerequisites"):
				if field_name in self.fields:
					self.fields[field_name].queryset = self.fields[field_name].queryset.exclude(
						pk=self.instance.pk
					)

		self.fields["insert_after"].label_from_instance = self._entry_label

	@staticmethod
	def _entry_label(entry):
		"""Label the chooser with the track, so lanes are distinguishable at a glance."""
		return f"{entry.track.name} - {entry}"

	def clean(self):
		cleaned_data = super().clean()
		track = cleaned_data.get("track")
		anchor = cleaned_data.get("insert_after")

		# Same column, not necessarily the same track: sagas that continue one
		# another share a column, and an entry from one can be slotted between
		# two from the other.
		if anchor and track and anchor.track_id != track.pk:
			column = {chain_track.pk for chain_track in track.column_tracks()}
			if anchor.track_id not in column:
				raise ValidationError(
					{"insert_after": f"'{anchor}' is in the {anchor.track} column, not {track}'s. "
					                 f"Pick an entry from the same column."}
				)

		if track:
			submitted = cleaned_data.get("position")
			if anchor:
				# An explicit "put it after this" beats anything else on the form.
				try:
					cleaned_data["position"] = next_position_after(anchor)
				except ValidationError as error:
					raise ValidationError({"insert_after": error.messages})
			elif submitted is not None:
				cleaned_data["position"] = submitted
			elif self.instance.position is None or self.instance.track_id != track.pk:
				# New entry, or moved to a different track: append to the end.
				cleaned_data["position"] = append_position(track)
			else:
				cleaned_data["position"] = self.instance.position

		self._autofill_poster(cleaned_data)
		self._validate_prerequisites(cleaned_data)
		return cleaned_data

	def _autofill_poster(self, cleaned_data):
		"""Find the committed poster for this title so nobody types a path.

		Only fills a blank field, so a hand-picked path is never overwritten. A
		title with no matching file just stays blank and renders as a text card;
		`link_watch_posters` reports those.
		"""
		if cleaned_data.get("poster_path"):
			return
		match = find_poster(cleaned_data.get("title"), cleaned_data.get("release_year"))
		if match:
			cleaned_data["poster_path"] = match

	def _validate_prerequisites(self, cleaned_data):
		prerequisites = cleaned_data.get("prerequisites")
		if not prerequisites:
			return

		probe = WatchEntry(
			pk=self.instance.pk,
			track=cleaned_data.get("track"),
			position=cleaned_data.get("position"),
		)
		if would_create_cycle(probe, [entry.pk for entry in prerequisites]):
			raise ValidationError(
				{"prerequisites": "These prerequisites create a loop - something would have to "
				                  "come both before and after itself. Check for a prerequisite "
				                  "that points backwards along its own track."}
			)
