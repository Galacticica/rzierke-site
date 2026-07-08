"""Unit tests for the development_portfolio page views."""

import datetime

import pytest
from django.urls import reverse

from development_portfolio.models import Bot, Project, Resource, Skill

pytestmark = pytest.mark.django_db


class TestDevHomeView:
    def test_returns_200_with_skills_in_context(self, client):
        skill = Skill.objects.create(name="Python", date_started=datetime.date(2020, 1, 1))
        response = client.get(reverse("dev-home"))
        assert response.status_code == 200
        assert list(response.context["skills"]) == [skill]
        assert "development_portfolio/dev_main.html" in [t.name for t in response.templates]


class TestDevPortfolioListView:
    def test_full_page_template_for_regular_request(self, client):
        Project.objects.create(project_name="Alpha")
        response = client.get(reverse("dev-project-list"))
        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "development_portfolio/dev_project_list.html" in template_names

    def test_htmx_request_renders_partial(self, client, htmx_headers):
        Project.objects.create(project_name="Alpha")
        response = client.get(reverse("dev-project-list"), **htmx_headers)
        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "development_portfolio/partials/project_results.html" in template_names
        assert "development_portfolio/dev_project_list.html" not in template_names

    def test_counts_with_q_filter(self, client):
        Project.objects.create(project_name="Django Site")
        Project.objects.create(project_name="Rust CLI")
        response = client.get(reverse("dev-project-list"), {"q": "django"})
        assert response.status_code == 200
        assert response.context["total_count"] == 2
        assert response.context["filtered_count"] == 1
        assert response.context["q"] == "django"
        assert [p.project_name for p in response.context["projects"]] == ["Django Site"]

    def test_counts_without_filter(self, client):
        Project.objects.create(project_name="Alpha")
        Project.objects.create(project_name="Beta")
        response = client.get(reverse("dev-project-list"))
        assert response.context["total_count"] == 2
        assert response.context["filtered_count"] == 2
        assert response.context["q"] == ""


class TestDevProjectDetailView:
    def test_detail_by_slug_returns_200(self, client):
        project = Project.objects.create(project_name="Alpha Project")
        response = client.get(reverse("dev-project-detail", kwargs={"slug": project.slug}))
        assert response.status_code == 200
        assert response.context["project"] == project

    def test_unknown_slug_returns_404(self, client):
        response = client.get(reverse("dev-project-detail", kwargs={"slug": "no-such-project"}))
        assert response.status_code == 404


class TestResourcesView:
    def test_returns_200_with_resources(self, client):
        resource = Resource.objects.create(name="Django Docs", url="https://docs.djangoproject.com/")
        response = client.get(reverse("dev-resources"))
        assert response.status_code == 200
        assert list(response.context["resources"]) == [resource]


class TestBotGraveyardView:
    def test_returns_200(self, client):
        response = client.get(reverse("dev-bot-graveyard"))
        assert response.status_code == 200
        assert response.context["bots_with_styles"] == []

    def test_styles_cycle_after_eight_bots(self, client):
        for i in range(9):
            Bot.objects.create(name=f"Bot {i}")
        response = client.get(reverse("dev-bot-graveyard"))
        styles = [entry["style"] for entry in response.context["bots_with_styles"]]
        assert styles[:8] == [f"style-{n}" for n in range(1, 9)]
        # The ninth bot wraps back around to style-1.
        assert styles[8] == "style-1"
