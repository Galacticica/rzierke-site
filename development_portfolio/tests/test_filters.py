"""Unit tests for the ProjectFilter filterset."""

import pytest

from development_portfolio.filters import ProjectFilter
from development_portfolio.models import Project, Tool

pytestmark = pytest.mark.django_db


@pytest.fixture
def projects():
    django_site = Project.objects.create(
        project_name="Django Site",
        event="Hackathon 2026",
        category="Web",
    )
    django_site.tool_used.add(Tool.objects.create(name="Python"))

    game = Project.objects.create(
        project_name="Space Game",
        event="Game Jam",
        category="Game",
    )
    game.tool_used.add(Tool.objects.create(name="Godot"))
    return {"django_site": django_site, "game": game}


class TestProjectFilter:
    def test_no_data_returns_all_projects(self, projects):
        filtered = ProjectFilter({}, queryset=Project.objects.all())
        assert filtered.qs.count() == 2

    def test_blank_q_returns_all_projects(self, projects):
        filtered = ProjectFilter({"q": ""}, queryset=Project.objects.all())
        assert filtered.qs.count() == 2

    def test_q_matches_project_name(self, projects):
        filtered = ProjectFilter({"q": "django"}, queryset=Project.objects.all())
        assert list(filtered.qs) == [projects["django_site"]]

    def test_q_matches_event(self, projects):
        filtered = ProjectFilter({"q": "hackathon"}, queryset=Project.objects.all())
        assert list(filtered.qs) == [projects["django_site"]]

    def test_q_matches_category(self, projects):
        filtered = ProjectFilter({"q": "web"}, queryset=Project.objects.all())
        assert list(filtered.qs) == [projects["django_site"]]

    def test_q_matches_tool_name(self, projects):
        filtered = ProjectFilter({"q": "godot"}, queryset=Project.objects.all())
        assert list(filtered.qs) == [projects["game"]]

    def test_q_no_match_returns_empty(self, projects):
        filtered = ProjectFilter({"q": "nonexistent"}, queryset=Project.objects.all())
        assert filtered.qs.count() == 0

    def test_q_result_is_distinct_with_multiple_tool_matches(self, projects):
        projects["game"].tool_used.add(Tool.objects.create(name="Godot Shaders"))
        filtered = ProjectFilter({"q": "godot"}, queryset=Project.objects.all())
        assert list(filtered.qs) == [projects["game"]]

    def test_only_q_field_is_declared(self):
        assert list(ProjectFilter.base_filters) == ["q"]
