"""Cache invalidation hooks for graph data."""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .graph_service import MCUGraphService
from .models import (
    Character, Relationship, WatchCollection, WatchEntry, WatchOrderConfig, WatchTrack,
)
from .watch_order_service import WatchOrderService


@receiver(post_save, sender=Character)
@receiver(post_save, sender=Relationship)
def invalidate_graph_cache(sender, **kwargs):
    MCUGraphService.invalidate_cache()


# The watch order keeps its own cache version so that editing a character does
# not throw away the chart payload, and vice versa.
@receiver(post_save, sender=WatchEntry)
@receiver(post_save, sender=WatchTrack)
@receiver(post_save, sender=WatchCollection)
@receiver(post_save, sender=WatchOrderConfig)
@receiver(post_delete, sender=WatchEntry)
@receiver(post_delete, sender=WatchTrack)
@receiver(post_delete, sender=WatchCollection)
def invalidate_watch_order_cache(sender, **kwargs):
    WatchOrderService.invalidate_cache()


@receiver(m2m_changed, sender=WatchEntry.prerequisites.through)
@receiver(m2m_changed, sender=WatchEntry.collections.through)
def invalidate_watch_order_cache_on_membership(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        WatchOrderService.invalidate_cache()