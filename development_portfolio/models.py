"""
File: models.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-15
Description: The models for the development portfolio section of the website. 
"""


from django.db import models
from django.db.models import Q
from django.utils.text import slugify

class ProjectQuerySet(models.QuerySet):
    """Custom QuerySet for Project model with additional filtering methods."""

    def with_related(self):
        return self.prefetch_related("tool_used", "images")

    def search(self, query: str | None):
        """Filter projects by a free-text query.

        Matches against project name, description, event, category, and tools used.
        """
        q = (query or "").strip()
        if not q:
            return self

        return (
            self.filter(
                Q(project_name__icontains=q)
                | Q(description__icontains=q)
                | Q(event__icontains=q)
                | Q(category__icontains=q)
                | Q(tool_used__name__icontains=q)
            )
            .distinct()
        )

class Project(models.Model):
    project_name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True, help_text="A brief description of the project.")
    event = models.CharField(max_length=200, blank=True, help_text="The event or context for the project.")
    date = models.DateField(null=True, blank=True, help_text="The date of the project or event.")
    category = models.CharField(max_length=100, blank=True, help_text="The category or type of project.")
    tool_used = models.ManyToManyField('Tool', blank=True, related_name='projects_using_tool',
                                       help_text="Tools used in the project.")
    public = models.BooleanField(default=False, help_text="Whether the project is publicly visible.")

    objects = ProjectQuerySet.as_manager()

    def __str__(self):
        return self.project_name
    
    def _generate_unique_slug(self) -> str:
        base_slug = slugify(self.project_name)
        slug = base_slug
        num = 1
        while Project.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{num}"
            num += 1
        return slug
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)


class ProjectImage(models.Model):
    image_source = models.CharField(max_length=200)
    image_alt_text = models.CharField(max_length=200, blank=True, help_text="Alternative text for the image.")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')

    def __str__(self):
        return f"Image for {self.project.project_name} from {self.image_source}"


class Tool(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name