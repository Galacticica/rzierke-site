'''
File: models.py
Project: rzierke-site
Created Date: 2026-05-25
Author: Reagan Zierke
Email: reaganzierke@gmail.com
-----
Last Modified: 2026-06-06 21:44:47
Modified By: Reagan Zierke
-----
Description: <<description>>
'''

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

class Character(models.Model):

    STATUS_CHOICES = [
        ('Alive', 'Alive'),
        ('Deceased', 'Deceased'),
        ('Unknown', 'Unknown'),
    ]

    ALIGNMENT_CHOICES = [
        ('Hero', 'Hero'),
        ('Villain', 'Villain'),
        ('Neutral', 'Neutral'),
        ('Reformed', 'Reformed'),
        ('Fallen', 'Fallen'),
    ]

    name = models.CharField(max_length=100, null=False, blank=False)
    phase_introduced = models.IntegerField(null=True, blank=True)
    movie_introduced = models.ForeignKey('Movie', on_delete=models.SET_NULL, null=True, blank=True, related_name='introduced_characters')
    alignment = models.CharField(max_length=100, choices=ALIGNMENT_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, null=True, blank=True)
    earth_number = models.ForeignKey('Earth', on_delete=models.SET_NULL, null=True, blank=True, related_name='characters')
    photo_path = models.CharField(max_length=500, blank=True, help_text="Path to a photo of the character.")

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if self.photo_path and not self.photo_path.endswith('.png'):
            self.photo_path += '.png'
        if self.photo_path and not self.photo_path.startswith('connections/'):
            self.photo_path = 'connections/' + self.photo_path
        super().save(*args, **kwargs)
    
    
class Earth(models.Model):
    number = models.CharField(max_length=50, unique=True, null=False, blank=False)
    
    def __str__(self):
        return self.number
    
class AlterEgo(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='alter_egos')
    name = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return f"{self.name} (Alter Ego of {self.character.name})"

class Team(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return self.name
    
class TeamMembership(models.Model):
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='team_memberships')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    is_current_member = models.BooleanField(default=True)

    def __str__(self):
        status = "Current" if self.is_current_member else "Former"
        return f"{self.character.name} - {self.team.name} ({status})"

class Movie(models.Model):
    title = models.CharField(max_length=200, null=False, blank=False)
    release_date = models.DateField()
    characters = models.ManyToManyField(Character, related_name='movies', blank=True)

    def __str__(self):
        return self.title

class Relationship(models.Model):

    RELATIONSHIP_CHOICES = [
        ('Ally', 'Ally'),
        ('Enemy', 'Enemy'),
        ('Family', 'Family'),
        ('Romantic', 'Romantic'),
        ('Mentor', 'Mentor'),
        ('Acquaintance', 'Acquaintance'),
        ('Variant', 'Variant'),
        ('Creation', 'Creation'),
    ]

    WEIGHTS = {
        'Variant':  1,
        'Family':   2,
        'Creation':  2,
        'Romantic': 3,
        'Ally':     4,
        'Mentor':   4,
        'Enemy':    6,
        'Acquaintance': 5,
    }

    character1 = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='relationships_as_character1')
    character2 = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='relationships_as_character2')
    relationship_type = models.CharField(max_length=100, choices=RELATIONSHIP_CHOICES)
    directional = models.BooleanField(default=False)
    weight = models.IntegerField(default=1)
    notes = models.TextField(blank=True)

    def __str__(self):
        direction = "->" if self.directional else "<->"
        return f"{self.character1.name} {direction} {self.character2.name} ({self.relationship_type})"

    def save(self, *args, **kwargs):
        self.weight = self.WEIGHTS.get(self.relationship_type, 1)
        super().save(*args, **kwargs)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['character1', 'character2', 'relationship_type'],
                name='unique_relationship'
            )
        ]


class BulkAddConfig(models.Model):
    """Singleton-ish config to control the connections bulk-add initial rows."""
    default_rows = models.IntegerField(default=15)

    class Meta:
        verbose_name = "Bulk Add Configuration"
        verbose_name_plural = "Bulk Add Configuration"

    def __str__(self):
        return f"Bulk add initial rows: {self.default_rows}"


# --------------------------------------------------------------------------
# Watch order chart
# --------------------------------------------------------------------------

# Positions are sparse on purpose: new entries land on multiples of this gap so
# there is always room to insert between two neighbours without renumbering
# them. See next_position_after().
POSITION_GAP = Decimal('10')

# Must match WatchEntry.position's decimal_places.
POSITION_QUANTUM = Decimal('0.000001')


class WatchTrack(models.Model):
    """A lane in the watch-order chart, usually a studio or a spin-off branch."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    color = models.CharField(
        max_length=7,
        default='#8B5CF6',
        help_text="Hex color used for this lane's arrows and badge.",
    )
    lane_order = models.IntegerField(default=0, help_text="Left-to-right position of the lane.")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide the lane without deleting it.")
    continues_from = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='continued_by',
        help_text="Pick the track this one carries on from, e.g. Multiverse Saga continues "
                  "Infinity Saga. They share a column, stacked in order, chained end to start. "
                  "Leave blank for a track that starts its own column.",
    )

    class Meta:
        ordering = ('lane_order', 'name')

    def __str__(self):
        return self.name

    def clean(self):
        """A track cannot continue itself, directly or round a loop."""
        super().clean()
        if not self.continues_from_id:
            return
        if self.continues_from_id == self.pk:
            raise ValidationError({'continues_from': "A track cannot continue itself."})

        seen = {self.pk}
        track = self.continues_from
        while track is not None:
            if track.pk in seen:
                raise ValidationError(
                    {'continues_from': "That would make the tracks continue each other in a loop."}
                )
            seen.add(track.pk)
            track = track.continues_from

    def column_root(self):
        """The track at the head of this column.

        A column is a run of tracks joined by continues_from. Guarded against a
        loop so a bad edit can never hang a page render.
        """
        seen = {self.pk}
        track = self
        while track.continues_from_id and track.continues_from_id not in seen:
            track = track.continues_from
            seen.add(track.pk)
        return track

    def column_tracks(self):
        """Every track sharing this column, head first."""
        chain, seen = [], set()
        track = self.column_root()
        while track is not None and track.pk not in seen:
            chain.append(track)
            seen.add(track.pk)
            track = WatchTrack.objects.filter(continues_from=track).first()
        return chain


class WatchCollection(models.Model):
    """A curated cross-track list, e.g. "Doomsday Prep".

    Independent of `track`: a lane says which branch of the story an entry lives
    on and it can only be one, while an entry can appear in any number of
    collections. Selecting one filters the chart down to its members.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, help_text="Shown when this collection is selected.")
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('display_order', 'name')

    def __str__(self):
        return self.name


class WatchEntry(models.Model):
    """A film, series, or special occupying one tile in the watch-order chart."""

    MEDIA_CHOICES = [
        ('Film', 'Film'),
        ('Series', 'Series'),
        ('Special', 'Special'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    track = models.ForeignKey(WatchTrack, on_delete=models.PROTECT, related_name='entries')
    position = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        db_index=True,
        help_text="Sparse ordering key within the track. Leave blank to append to the end.",
    )
    media_type = models.CharField(max_length=20, choices=MEDIA_CHOICES, default='Film')
    release_year = models.IntegerField(null=True, blank=True, help_text="Display only - never used for ordering.")
    runtime_minutes = models.IntegerField(null=True, blank=True, help_text="Feeds the 'hours remaining' counter.")
    episode_count = models.IntegerField(null=True, blank=True, help_text="For series, used with runtime as a per-episode figure.")
    poster_path = models.CharField(
        max_length=300,
        blank=True,
        help_text="Static path to the poster, e.g. watch-order/iron-man.jpg. Blank renders a text card.",
    )
    note = models.TextField(blank=True, help_text="Shown in the detail card.")
    movie = models.ForeignKey(
        'Movie',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='watch_entries',
        help_text="Optional link to the same title in the character graph.",
    )
    prerequisites = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='unlocks',
        help_text="Entries that must come first. Only needed for merges across tracks - "
                  "order inside a single track comes from position.",
    )
    collections = models.ManyToManyField(
        WatchCollection,
        blank=True,
        related_name='entries',
        help_text="Curated lists this belongs to. An entry can be in as many as you like.",
    )
    is_published = models.BooleanField(default=True, help_text="Uncheck to keep the entry off the public chart.")
    connects_to_previous = models.BooleanField(
        default=True,
        help_text="Uncheck to break the arrow coming in from the entry above. It still takes "
                  "the next slot on the chart - only the arrow goes away.",
    )

    tmdb_id = models.IntegerField(
        null=True, blank=True, db_index=True,
        help_text="Set automatically on the first lookup. Correct it by hand to fix a wrong match.",
    )
    tmdb_type = models.CharField(
        max_length=10, blank=True,
        choices=[('movie', 'movie'), ('tv', 'tv')],
        help_text="Which TMDB endpoint this came from.",
    )
    tmdb_season = models.IntegerField(
        null=True, blank=True,
        help_text="For a single season of a series. Parsed from a title like "
                  "'Daredevil Season 1' when left blank; blank on a non-season title means the whole show.",
    )

    class Meta:
        ordering = ('track__lane_order', 'position', 'pk')
        verbose_name_plural = 'Watch entries'
        indexes = [
            # Deliberately not unique: exhausted midpoints and renormalization
            # must never raise IntegrityError. pk is the stable tiebreak.
            models.Index(fields=['track', 'position'], name='watchentry_track_position'),
        ]

    def __str__(self):
        if self.release_year:
            return f"{self.title} ({self.release_year})"
        return self.title

    def save(self, *args, **kwargs):
        if self.poster_path and not self.poster_path.startswith('watch-order/'):
            self.poster_path = 'watch-order/' + self.poster_path
        if self.position is None:
            self.position = append_position(self.track)
        super().save(*args, **kwargs)

    @property
    def total_minutes(self):
        """Runtime for the whole entry, multiplying through episodes for a series."""
        if not self.runtime_minutes:
            return 0
        return self.runtime_minutes * (self.episode_count or 1)


class WatchProgress(models.Model):
    """Marks one entry as watched by one signed-in user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='watch_progress')
    entry = models.ForeignKey(WatchEntry, on_delete=models.CASCADE, related_name='progress')
    watched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Watch progress'
        constraints = [
            models.UniqueConstraint(fields=['user', 'entry'], name='unique_user_watch_entry')
        ]

    def __str__(self):
        return f"{self.user} watched {self.entry.title}"


class WatchOrderConfig(models.Model):
    """Singleton-ish display settings for the watch-order chart."""

    items_per_row = models.IntegerField(
        default=0,
        help_text="How many entries sit side by side before the list wraps onto the next row. "
                  "The order reads left to right, then down, like a page of text. "
                  "0 disables wrapping and keeps one entry per row, running straight down.",
    )

    class Meta:
        verbose_name = "Watch Order Configuration"
        verbose_name_plural = "Watch Order Configuration"

    def __str__(self):
        if self.items_per_row:
            return f"{self.items_per_row} across, then wrap"
        return "No wrapping"

    @classmethod
    def current(cls):
        return cls.objects.first() or cls()


def column_entries(track):
    """Every entry in `track`'s column, whichever track inside it they belong to.

    Position is scoped to the column, not the track, so that two tracks sharing
    a column can interleave - a Multiverse Saga entry can sit between two
    Infinity Saga ones, which is the normal case for anything released out of
    story order.
    """
    return WatchEntry.objects.filter(track__in=track.column_tracks())


def append_position(track):
    """Position that puts a new entry at the end of `track`'s column."""
    last = column_entries(track).order_by('-position', '-pk').first()
    if last is None:
        return POSITION_GAP
    return last.position + POSITION_GAP


def next_position_after(entry):
    """Position that places a new entry directly after `entry` in its column.

    Returns the midpoint between `entry` and whatever currently follows it, so
    inserting never touches the neighbours. Appends past the end when `entry`
    is last.
    """
    following = (
        column_entries(entry.track)
        .filter(position__gt=entry.position)
        .order_by('position', 'pk')
        .first()
    )
    if following is None:
        return entry.position + POSITION_GAP

    midpoint = ((entry.position + following.position) / 2).quantize(POSITION_QUANTUM)
    if midpoint <= entry.position or midpoint >= following.position:
        # Six decimal places used up between these two neighbours. Renormalizing
        # the column spreads everything back out to 10, 20, 30...
        raise ValidationError(
            f"No room left between '{entry}' and '{following}'. "
            f"Renormalize the '{entry.track}' column first, then try again."
        )
    return midpoint


def renormalize_track(track):
    """Rewrite a column's positions to 10, 20, 30... preserving current order.

    Current order means what the chart draws today: tracks in chain order, and
    entries by position inside each. That makes this safe to run on a column
    whose two tracks still carry independent numbering - nothing moves, it just
    becomes one sequence that can then be interleaved.

    Uses bulk_update, so it does not fire post_save. Callers are responsible for
    invalidating the watch-order cache.
    """
    chain = track.column_tracks()
    order = {chain_track.pk: index for index, chain_track in enumerate(chain)}

    entries = sorted(
        column_entries(track),
        key=lambda entry: (order.get(entry.track_id, 0), entry.position, entry.pk),
    )
    for index, entry in enumerate(entries, start=1):
        entry.position = POSITION_GAP * index

    with transaction.atomic():
        WatchEntry.objects.bulk_update(entries, ['position'])
    return len(entries)