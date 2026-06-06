'''
File: models.py
Project: rzierke-site
Created Date: 2026-05-25
Author: Reagan Zierke
Email: reaganzierke@gmail.com
-----
Last Modified: 2026-05-26 20:48:37
Modified By: Reagan Zierke
-----
Description: <<description>>
'''

from django.db import models

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
    latest_appearance = models.ForeignKey('Movie', on_delete=models.SET_NULL, null=True, blank=True, related_name='latest_characters')
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