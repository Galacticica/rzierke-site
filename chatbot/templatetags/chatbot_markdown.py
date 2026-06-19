"""
File: chatbot_markdown.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Description: Template filter that renders AI message content (stored as raw
markdown) into sanitized HTML so responses display with proper formatting.
"""

from __future__ import annotations

import markdown as md
import nh3
from django.template import Library
from django.utils.safestring import mark_safe

register = Library()

# Tags the rendered markdown is allowed to produce. Everything else is stripped
# by nh3 before the HTML is marked safe, so raw HTML in a model response can't
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


@register.filter(name="render_markdown")
def render_markdown(value: str | None):
    """Convert markdown text to sanitized HTML for safe display in templates."""
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
