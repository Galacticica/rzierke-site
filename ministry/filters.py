"""
File: filters.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-03
Description: description
"""


# filters.py
import django_filters as django_filter
from django import forms

from .models import Song, Artist, Tag


class SongFilter(django_filter.FilterSet):
    q = django_filter.CharFilter(
        method="filter_q",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Title, artist, LSB, CCLI",
            }
        ),
    )
    lsb_only = django_filter.BooleanFilter(
        method="filter_lsb_only",
        label="LSB only",
        widget=forms.CheckboxInput(attrs={"class": "checkbox"}),
    )

    artist = django_filter.ModelMultipleChoiceFilter(
        field_name="artist",                
        queryset=Artist.objects.all(),
        conjoined=False,                     
        label="Artists",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "space-y-2",
            }
        ),
    )

    tag = django_filter.ModelMultipleChoiceFilter(
        field_name="tag",                    
        queryset=Tag.objects.all(),
        conjoined=False,                     
        label="Tags",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "space-y-2",
            }
        ),
    )

    class Meta:
        model = Song
        fields = ["q", "lsb_only", "artist", "tag"]

    def filter_q(self, qs, name, value):
        return qs.search(value)

    def filter_lsb_only(self, qs, name, value):
        if not value:
            return qs
        return qs.exclude(lsb_number__isnull=True).exclude(lsb_number__exact="")

