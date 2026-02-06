"""
File: devo_format.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: Template filters for formatting devotion content. 
- Provides consistent paragraph wrapping and spacing.
"""


import re

from django import template
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def devo_paragraphs(value: str | None):
    """Render devotion content with consistent wrapping.

    - Treat blank lines as paragraph breaks.
    - Treat single newlines inside a paragraph as spaces (prevents awkward short/long lines).
    """
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]

    def normalize_paragraph(p: str) -> str:
        p = re.sub(r"[\t\n]+", " ", p)
        p = re.sub(r"\s{2,}", " ", p)
        return p.strip()

    escaped_paragraphs = [(conditional_escape(normalize_paragraph(p)),) for p in paragraphs]

    html = format_html_join(
        "",
        '<p class="mb-4 last:mb-0">{}</p>',
        escaped_paragraphs,
    )
    return mark_safe(html)
