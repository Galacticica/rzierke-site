"""
File: models.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-02
Description: This file contains the models for song resources used in ministry.
"""

from django.db import models
from django.db.models import Q
from django.utils.text import slugify

class SongQuerySet(models.QuerySet):
    def with_display_related(self):
        return self.prefetch_related("artist", "tag", "arrangement_items__section")

    def search(self, query: str | None):
        """Filter songs by a free-text query.

        Matches against title, artist name, LSB number, and CCLI number.
        """
        q = (query or "").strip()
        if not q:
            return self

        return (
            self.filter(
                Q(title__icontains=q)
                | Q(artist__name__icontains=q)
                | Q(lsb_number__icontains=q)
                | Q(ccli_number__icontains=q)
            )
            .distinct()
        )


class Song(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    artist = models.ManyToManyField('Artist', blank=True, related_name='artist_songs')
    lsb_number = models.CharField(max_length=10, null=True, blank=True, unique=True,
                                  help_text="Lutheran Service Book number, if applicable.")
    ccli_number = models.CharField(max_length=10, null=True, blank=True, unique=True,
                                   help_text="CCLI number, if applicable.")
    tag = models.ManyToManyField('Tag', blank=True, related_name='tagged_songs',
                                 help_text="Tags for categorizing songs.")
    public_domain = models.BooleanField(default=False,
                                        help_text="Indicates if the song is in the public domain.")

    objects = SongQuerySet.as_manager()

    def __str__(self):
        return self.title

    def _generate_unique_slug(self) -> str:
        """
        Create a unique slug from the title (and disambiguate with -2, -3, etc.).
        """
        base = slugify(self.title)[:200] or "song"
        slug = base
        i = 2

        # Exclude self when editing an existing object
        qs = Song.objects.all()
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        while qs.filter(slug=slug).exists():
            suffix = f"-{i}"
            slug = f"{base[:220 - len(suffix)]}{suffix}"
            i += 1

        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    

class Artist(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Tag(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class SectionDefinition(models.Model):

    VERSE = "verse"
    CHORUS = "chorus"
    BRIDGE = "bridge"
    PRECHORUS = "prechorus"
    TAG = "tag"
    INTRO = "intro"
    OUTRO = "outro"
    INSTRUMENTAL = "instrumental"

    SECTION_TYPES = [
        (VERSE, "Verse"),
        (CHORUS, "Chorus"),
        (PRECHORUS, "Pre-Chorus"),
        (BRIDGE, "Bridge"),
        (TAG, "Tag"),
        (INTRO, "Intro"),
        (OUTRO, "Outro"),
        (INSTRUMENTAL, "Instrumental"),
    ]

    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='sections')
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES, default=VERSE)
    name = models.CharField(max_length=100, null=True, blank=True, help_text="Optional custom name for the section. E.g., 'Chorus', 'Verse 1'.")
    lyrics = models.TextField(help_text="Lyrics for this section. Use line breaks to separate lines. Use double line breaks to separate slides.")

    def __str__(self):
        return f"{self.song.title} - {self.name or self.get_section_type_display()}"


class ArrangementItem(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='arrangement_items')
    section = models.ForeignKey(SectionDefinition, on_delete=models.CASCADE, related_name='arrangement_items')
    order = models.PositiveIntegerField(help_text="Order of this section in the arrangement.")
    repeat_count = models.PositiveIntegerField(default=1, help_text="Number of times to repeat this section.")

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['song', 'order'], name='uniq_song_arrangement_order'),
        ]
    
    def __str__(self):
        return f"{self.song.title} - {self.section.section_type} (Order: {self.order}, Repeats: {self.repeat_count})"




    