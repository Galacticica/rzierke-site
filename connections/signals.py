"""Cache invalidation hooks for graph data."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .graph_service import MCUGraphService
from .models import Character, Relationship


@receiver(post_save, sender=Character)
@receiver(post_save, sender=Relationship)
def invalidate_graph_cache(sender, **kwargs):
    MCUGraphService.invalidate_cache()