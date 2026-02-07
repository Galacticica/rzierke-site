"""
File: models.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-07
Description: The models for performances and pieces.
"""


from django.db import models
from django.db.models import Q

class PieceQuerySet(models.QuerySet):
    def with_performers(self):
        return self.prefetch_related("performer")
    
    def with_display_related(self):
        return self.prefetch_related("performer", "instrument", "piece_type")
    
    def search(self, query: str | None):
        """Filter pieces by a free-text query.
        
        Matches against title and composer.
        """
        q = (query or "").strip()
        if not q:
            return self
        
        return self.filter(
            Q(title__icontains=q)
            | Q(composer__icontains=q)
        ).distinct()

class Piece(models.Model):
    title = models.CharField(max_length=200)
    composer = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    public = models.BooleanField(default=True)
    date_performed = models.DateField(null=True, blank=True)
    performer = models.ManyToManyField('Performer', blank=True)
    piece_type = models.ForeignKey('PieceType', on_delete=models.SET_NULL, null=True, blank=True)
    instrument = models.ManyToManyField('Instrument', blank=True)
    recording_url = models.URLField(blank=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    objects = PieceQuerySet.as_manager()

    def __str__(self):
        return f"{self.title} by {self.composer}"
    
    def _generate_unique_slug(self) -> str:
        """
        Create a unique slug from the title (and disambiguate with -2, -3, etc.).
        """
        from django.utils.text import slugify
        base = slugify(self.title)[:200] or "piece"
        slug = base
        i = 2

        qs = Piece.objects.all()
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
    
class Performer(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name
    
class Instrument(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name
    
class PieceType(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name




