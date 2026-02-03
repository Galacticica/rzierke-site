"""
File: models.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-02
Description: This file contains the models for song resources used in ministry.
"""

from django.db import models

class Song(models.Model):
    title = models.CharField(max_length=200)
    artist = models.ManyToManyField('Artist', blank=True, null=True, related_name='artist_songs')   
    lsb_number = models.CharField(max_length=10, null=True, blank=True, unique=True, help_text="Lutheran Service Book number, if applicable.")
    ccli_number = models.CharField(max_length=10, null=True, blank=True, unique=True, help_text="CCLI number, if applicable.")
    tag = models.ManyToManyField('Tag', blank=True, null=True, related_name='tagged_songs', help_text="Tags for categorizing songs.")

class Artist(models.Model):
    name = models.CharField(max_length=100)

class Tag(models.Model):
    name = models.CharField(max_length=50)


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
    section_type = models.CharField(max_length=20, choices=SECTION_TYPES)
    name = models.CharField(max_length=100, null=True, blank=True, help_text="Optional custom name for the section. E.g., 'Chorus', 'Verse 1'.")
    lyrics = models.TextField(help_text="Lyrics for this section. Use line breaks to separate lines. Use double line breaks to separate slides.")


class ArrangementItem(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='arrangement_items')
    section = models.ForeignKey(SectionDefinition, on_delete=models.CASCADE, related_name='arrangement_items')
    order = models.PositiveIntegerField(help_text="Order of this section in the arrangement.")
    repeat_count = models.PositiveIntegerField(default=1, help_text="Number of times to repeat this section.")

    class Meta:
        ordering = ['order']




    