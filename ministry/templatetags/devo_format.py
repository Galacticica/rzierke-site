"""
File: devo_format.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: Template filters for formatting devotion content.
- Renders devotion content (stored as markdown) into sanitized HTML.
"""

from __future__ import annotations

import markdown as md
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Tags the rendered markdown is allowed to produce. Everything else is stripped
# by nh3 before the HTML is marked safe, so raw HTML in devotion content can't
# inject scripts/styles.
_ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li",
    "strong", "em", "del", "code", "pre",
    "blockquote",
    "a",
    "table", "thead", "tbody", "tr", "th", "td",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
}


@register.filter(name="devo_markdown")
def devo_markdown(value: str | None):
    """Convert devotion markdown to sanitized HTML for safe display."""
    if not value:
        return ""

    html = md.markdown(
        value,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html",
    )

    clean = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )

    return mark_safe(clean)
