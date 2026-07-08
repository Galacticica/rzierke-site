"""
File: test_portfolio.py
Description: Development portfolio project list: seeded projects render,
the q search filters via HTMX, and the detail page opens from a card.
"""

import pytest
from playwright.sync_api import Page, expect

PROJECTS_URL = "/development-portfolio/projects"


@pytest.fixture
def projects(db):
    from development_portfolio.models import Project

    return [
        Project.objects.create(
            project_name="Alpha Dashboard",
            short_description="Realtime metrics dashboard.",
            description="A dashboard that graphs realtime metrics.",
            category="Web",
        ),
        Project.objects.create(
            project_name="Beta Game",
            short_description="A small arcade game.",
            category="Game",
        ),
        Project.objects.create(
            project_name="Gamma Tool",
            short_description="A CLI utility.",
            category="Tooling",
        ),
    ]


def test_project_list_shows_seeded_projects(page: Page, live_server, projects):
    page.goto(live_server.url + PROJECTS_URL)

    results = page.locator("#project-results")
    expect(results.locator("article")).to_have_count(3)
    expect(results).to_contain_text("Alpha Dashboard")
    expect(results).to_contain_text("Beta Game")
    expect(results).to_contain_text("Gamma Tool")


def test_search_filters_to_one_project(page: Page, live_server, projects):
    page.goto(live_server.url + PROJECTS_URL)
    expect(page.locator("#project-results article")).to_have_count(3)

    page.fill('input[name="q"]', "Alpha")
    page.get_by_role("button", name="Search").click()

    results = page.locator("#project-results")
    expect(results.locator("article")).to_have_count(1)
    expect(results).to_contain_text("Alpha Dashboard")
    expect(results).not_to_contain_text("Beta Game")


def test_project_detail_opens_from_card(page: Page, live_server, projects):
    page.goto(live_server.url + PROJECTS_URL)

    card = page.locator("#project-results article", has_text="Alpha Dashboard")
    card.get_by_role("link", name="Open").click()

    expect(page).to_have_url(live_server.url + "/development-portfolio/projects/alpha-dashboard/")
    expect(page.get_by_role("heading", name="Alpha Dashboard")).to_be_visible()
    expect(page.locator("body")).to_contain_text("A dashboard that graphs realtime metrics.")
