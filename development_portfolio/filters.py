"""
File: filters.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-03
Description: Filtering logic for development portfolio resources.
"""

import django_filters as django_filter
from django import forms

from .models import Project

class ProjectFilter(django_filter.FilterSet):
    """A filter set for filtering Project instances based on various criteria."""
    q = django_filter.CharFilter(
        method="filter_q",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Title, description",
            }
        ),
    )

    class Meta:
        model = Project
        fields = ["q"]

    def filter_q(self, qs, name, value):
        return qs.search(value)