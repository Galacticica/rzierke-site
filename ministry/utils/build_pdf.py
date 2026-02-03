"""
File: build_pdf.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-03
Description: Creates PDF files for ministry songs.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from reportlab.lib.pagesizes import letter  # or A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_LEFT

from ministry.models import Song  # adjust app label if needed


@dataclass
class PrintBlock:
    label: str
    lyrics: str


def build_song_print_pdf_bytes(song: Song) -> bytes:
    """
    Printable PDF handout:
      - Title + meta at top (full width)
      - Two-column flowing body
      - Arrangement order respected
      - repeat_count duplicates sections
      - Lyrics are NOT split into slides; blank lines are paragraph breaks
    """
    buf = io.BytesIO()

    # ---- Doc + layout constants ----
    page_w, page_h = letter
    margin = 0.6 * inch
    gutter = 0.25 * inch  # space between columns
    header_h = 0.9 * inch  # reserved for title/meta

    # Two equal columns inside margins
    usable_w = page_w - 2 * margin
    col_w = (usable_w - gutter) / 2
    col_h = page_h - 2 * margin - header_h

    # Frames for body (two columns)
    left_frame = Frame(
        margin,
        margin,
        col_w,
        col_h,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="left",
    )
    right_frame = Frame(
        margin + col_w + gutter,
        margin,
        col_w,
        col_h,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="right",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "SongTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "SongMeta",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        textColor="#444444",
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "SectionLabel",
        parent=styles["Heading4"],
        fontSize=11,
        leading=13,
        spaceBefore=6,
        spaceAfter=2,
    )
    # Use <br/> line breaks; blank lines become extra Spacer via parsing below
    lyric_style = ParagraphStyle(
        "Lyrics",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=13,
        spaceAfter=6,
    )

    def header(canvas, doc):
        canvas.saveState()
        x = margin
        y = page_h - margin

        # Title
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(x, y - 18, song.title)

        # Meta line
        meta_parts = []

        artists = song.artist.all()
        if artists:
            meta_parts.append(", ".join(a.name for a in artists))

        if song.lsb_number:
            meta_parts.append(f"LSB {song.lsb_number}")

        if song.ccli_number:
            meta_parts.append(f"CCLI {song.ccli_number}")

        meta_text = " • ".join(meta_parts)

        if meta_text:
            canvas.setFont("Helvetica", 10)
            canvas.setFillGray(0.25)
            canvas.drawString(x, y - 36, meta_text)
            canvas.setFillGray(0)

        # Optional divider
        canvas.setLineWidth(0.5)
        canvas.setStrokeGray(0.7)
        canvas.line(margin, page_h - margin - header_h + 10, page_w - margin, page_h - margin - header_h + 10)
        canvas.setStrokeGray(0)

        canvas.restoreState()

    doc = BaseDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=f"{song.title} Lyrics",
        author="",
    )

    doc.addPageTemplates(
        [
            PageTemplate(
                id="TwoCol",
                frames=[left_frame, right_frame],
                onPage=header,
            )
        ]
    )

    # ---- Build arranged blocks ----
    items = song.arrangement_items.select_related("section").all()
    blocks: list[PrintBlock] = []

    for item in items:
        section = item.section
        label = section.name or section.get_section_type_display()
        lyrics = (section.lyrics or "").strip()

        for _ in range(item.repeat_count):
            blocks.append(PrintBlock(label=label, lyrics=lyrics))

    # ---- Story ----
    story = []

    # Add a little spacing under the header area on first frame content
    story.append(Spacer(1, 6))

    for b in blocks:
        section_flowables = []

        section_flowables.append(Paragraph(b.label, section_style))

        paragraphs = [
            p.strip()
            for p in (b.lyrics.replace("\r\n", "\n").replace("\r", "\n")).split("\n\n")
        ]

        for p in paragraphs:
            if not p:
                section_flowables.append(Spacer(1, 6))
                continue

            html = "<br/>".join(line.strip() for line in p.split("\n"))
            section_flowables.append(Paragraph(html, lyric_style))

        section_flowables.append(Spacer(1, 8))

        story.append(KeepTogether(section_flowables))


    doc.build(story)

    return buf.getvalue()

