"""
File: filters.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-07
Description: Filtering logic for piece resources in rzpercussion.
"""

import django_filters as django_filter
from django import forms

from .models import Piece, Instrument, PieceType


class PieceFilter(django_filter.FilterSet):
    """A filter set for filtering Piece instances based on various criteria."""
    q = django_filter.CharFilter(
        method="filter_q",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Title, composer",
            }
        ),
    )

    instrument = django_filter.ModelMultipleChoiceFilter(
        field_name="instrument",                
        queryset=Instrument.objects.all(),
        conjoined=False,                     
        label="Instruments",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "space-y-2",
            }
        ),
    )

    piece_type = django_filter.ModelMultipleChoiceFilter(
        field_name="piece_type",                    
        queryset=PieceType.objects.all(),
        conjoined=False,                     
        label="Piece Types",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "space-y-2",
            }
        ),
    )

    class Meta:
        model = Piece
        fields = ["q", "instrument", "piece_type"]

    def filter_q(self, qs, name, value):
        return qs.search(value)
