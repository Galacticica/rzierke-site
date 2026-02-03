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
    if text is None:
        return ""

    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    # Drop fully blank/whitespace-only lines.
    lines = [line for line in normalized.split("\n") if line.strip()]
    cleaned = "\n".join(lines)
    escaped = escape(cleaned)
    return mark_safe(escaped.replace("\n", "<br>\n"))


# Backwards-compatible alias: templates might use `|lyric_cleaner`.
@register.filter(name="lyric_cleaner")
def lyric_cleaner_filter(text):
    return lyrics_html(text)
