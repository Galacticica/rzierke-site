"""Unit tests for development_portfolio models."""

import datetime

import pytest
from django.urls import reverse

from development_portfolio.models import Project, Skill, Tool

pytestmark = pytest.mark.django_db


class TestProjectSlug:
    def test_slug_generated_from_name(self):
        project = Project.objects.create(project_name="My Cool Project")
        assert project.slug == "my-cool-project"

    def test_slug_collision_gets_numeric_suffix(self):
        Project.objects.create(project_name="My Project")
        second = Project.objects.create(project_name="My Project")
        third = Project.objects.create(project_name="My Project")
        assert second.slug == "my-project-1"
        assert third.slug == "my-project-2"

    def test_explicit_slug_is_kept(self):
        project = Project.objects.create(project_name="My Project", slug="custom-slug")
        assert project.slug == "custom-slug"

    def test_slug_not_regenerated_on_resave(self):
        project = Project.objects.create(project_name="My Project")
        project.project_name = "Renamed Project"
        project.save()
        project.refresh_from_db()
        assert project.slug == "my-project"


class TestProjectQuerySet:
    def test_search_blank_query_returns_everything(self):
        Project.objects.create(project_name="Alpha")
        Project.objects.create(project_name="Beta")
        assert Project.objects.search("").count() == 2
        assert Project.objects.search(None).count() == 2
        assert Project.objects.search("   ").count() == 2

    def test_search_matches_project_name(self):
        match = Project.objects.create(project_name="Django Site")
        Project.objects.create(project_name="Rust CLI")
        results = Project.objects.search("django")
        assert list(results) == [match]

    def test_search_matches_event(self):
        match = Project.objects.create(project_name="Alpha", event="Hackathon 2026")
        Project.objects.create(project_name="Beta", event="Class Project")
        assert list(Project.objects.search("hackathon")) == [match]

    def test_search_matches_category(self):
        match = Project.objects.create(project_name="Alpha", category="Web Development")
        Project.objects.create(project_name="Beta", category="Game")
        assert list(Project.objects.search("web")) == [match]

    def test_search_matches_tool_name(self):
        match = Project.objects.create(project_name="Alpha")
        match.tool_used.add(Tool.objects.create(name="Python"))
        Project.objects.create(project_name="Beta")
        assert list(Project.objects.search("python")) == [match]

    def test_search_does_not_match_description(self):
        Project.objects.create(project_name="Alpha", description="uniqueword here")
        assert Project.objects.search("uniqueword").count() == 0

    def test_search_is_distinct_across_multiple_matching_tools(self):
        project = Project.objects.create(project_name="Alpha")
        project.tool_used.add(
            Tool.objects.create(name="PyTest"),
            Tool.objects.create(name="Python"),
        )
        results = Project.objects.search("py")
        assert list(results) == [project]

    def test_with_related_returns_same_projects(self):
        project = Project.objects.create(project_name="Alpha")
        assert list(Project.objects.with_related()) == [project]


class TestProjectLiveLink:
    def test_prefers_url_name_when_set(self):
        project = Project.objects.create(
            project_name="Ministry Site",
            live_url_name="min-home",
            live_url="https://example.com/external/",
        )
        assert project.live_link == reverse("min-home")

    def test_bad_url_name_returns_empty_string_even_with_fallback_url(self):
        project = Project.objects.create(
            project_name="Broken",
            live_url_name="definitely-not-a-real-url-name",
            live_url="https://example.com/external/",
        )
        assert project.live_link == ""

    def test_falls_back_to_live_url_when_no_url_name(self):
        project = Project.objects.create(
            project_name="External",
            live_url="https://example.com/app/",
        )
        assert project.live_link == "https://example.com/app/"

    def test_empty_when_nothing_configured(self):
        project = Project.objects.create(project_name="Bare")
        assert project.live_link == ""


class TestSkillExperience:
    def _skill(self, days_ago: int) -> Skill:
        started = datetime.date.today() - datetime.timedelta(days=days_ago)
        return Skill.objects.create(name="Skill", date_started=started)

    def test_366_days_ago_is_one_year(self):
        skill = self._skill(366)
        assert skill.years_of_experience() == 1
        assert skill.experience_display() == "1 yr"

    def test_70_days_ago_shows_months(self):
        skill = self._skill(70)
        assert skill.years_of_experience() == 0
        # 70 days always spans exactly two whole calendar months and change.
        assert skill.experience_display() == "2 mos"

    def test_10_days_ago_floors_to_one_month_minimum(self):
        skill = self._skill(10)
        assert skill.years_of_experience() == 0
        # Zero whole months is bumped up to "1 mo" by experience_display.
        assert skill.experience_display() == "1 mo"

    def test_multiple_years_are_plural(self):
        skill = self._skill(3 * 366)
        assert skill.years_of_experience() == 3
        assert skill.experience_display() == "3 yrs"

    def test_364_days_ago_floors_to_zero_years(self):
        skill = self._skill(364)
        assert skill.years_of_experience() == 0
        assert skill.experience_display().endswith("mos")
