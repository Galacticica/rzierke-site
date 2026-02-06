"""
File: lyric_cleaner.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-02
Description: Makes lyric text cleaner for display.
"""

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name="lyrics_html")
def lyrics_html(text):
    """Cleans lyric text for HTML display."""
    if text is None:
        return ""

    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in normalized.split("\n") if line.strip()]
    cleaned = "\n".join(lines)
    escaped = escape(cleaned)
    return mark_safe(escaped.replace("\n", "<br>\n"))


@register.filter(name="lyric_cleaner")
def lyric_cleaner_filter(text):
    return lyrics_html(text)
