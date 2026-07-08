"""Unit tests for the Strudel editor and spin-the-wheel JSON/HTMX endpoints."""

import json

import pytest
from django.urls import reverse

from development_portfolio.models import StrudelProject, Wheel, WheelItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_user(db):
    from accounts.models import User

    return User.objects.create_user(email="other@example.com", password="password123")


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


class TestStrudelView:
    def test_editor_page_lists_projects(self, client, user):
        project = StrudelProject.objects.create(name="Beat", text="s('bd')", user=user)
        response = client.get(reverse("dev-strudel"))
        assert response.status_code == 200
        assert response.context["strudel_projects"] == [
            {"id": project.id, "name": "Beat", "user_id": user.id}
        ]


class TestStrudelProjectDetail:
    def test_missing_project_returns_404_json(self, client):
        response = client.get(reverse("strudel-project-detail", kwargs={"project_id": 9999}))
        assert response.status_code == 404
        assert response.json() == {"error": "Project not found."}

    def test_owner_can_edit(self, auth_client, user):
        project = StrudelProject.objects.create(name="Beat", text="s('bd')", user=user)
        response = auth_client.get(
            reverse("strudel-project-detail", kwargs={"project_id": project.id})
        )
        assert response.status_code == 200
        data = response.json()
        assert data["can_edit"] is True
        assert data["id"] == project.id
        assert data["name"] == "Beat"
        assert data["text"] == "s('bd')"
        assert data["user_id"] == user.id

    def test_anonymous_cannot_edit(self, client, user):
        project = StrudelProject.objects.create(name="Beat", user=user)
        response = client.get(
            reverse("strudel-project-detail", kwargs={"project_id": project.id})
        )
        assert response.status_code == 200
        assert response.json()["can_edit"] is False

    def test_other_user_cannot_edit(self, client, user, other_user):
        project = StrudelProject.objects.create(name="Beat", user=user)
        client.force_login(other_user)
        response = client.get(
            reverse("strudel-project-detail", kwargs={"project_id": project.id})
        )
        assert response.status_code == 200
        assert response.json()["can_edit"] is False


class TestStrudelProjectSave:
    url = reverse("strudel-project-save")

    def test_anonymous_gets_401(self, client):
        response = _post_json(client, self.url, {"name": "Beat", "text": "x"})
        assert response.status_code == 401
        assert response.json() == {"error": "Authentication required."}

    def test_invalid_json_body_returns_400(self, auth_client):
        response = auth_client.post(
            self.url, data="{not json", content_type="application/json"
        )
        assert response.status_code == 400
        assert response.json() == {"error": "Invalid JSON payload."}

    def test_blank_name_returns_400(self, auth_client):
        response = _post_json(auth_client, self.url, {"name": "   ", "text": "x"})
        assert response.status_code == 400
        assert response.json() == {"error": "Project name is required."}

    def test_create_new_project(self, auth_client, user):
        response = _post_json(auth_client, self.url, {"name": "New Beat", "text": "s('bd')"})
        assert response.status_code == 200
        data = response.json()
        project = StrudelProject.objects.get(id=data["id"])
        assert project.name == "New Beat"
        assert project.text == "s('bd')"
        assert project.user_id == user.id
        assert data["can_edit"] is True

    def test_empty_body_treated_as_empty_payload(self, auth_client):
        # The view falls back to "{}" for an empty body, so this is a blank name.
        response = auth_client.post(self.url, data="", content_type="application/json")
        assert response.status_code == 400
        assert response.json() == {"error": "Project name is required."}

    def test_update_own_project(self, auth_client, user):
        project = StrudelProject.objects.create(name="Old", text="old", user=user)
        response = _post_json(
            auth_client, self.url, {"id": project.id, "name": "New", "text": "new"}
        )
        assert response.status_code == 200
        project.refresh_from_db()
        assert project.name == "New"
        assert project.text == "new"
        assert StrudelProject.objects.count() == 1

    def test_update_someone_elses_project_returns_403(self, auth_client, other_user):
        project = StrudelProject.objects.create(name="Theirs", text="t", user=other_user)
        response = _post_json(
            auth_client, self.url, {"id": project.id, "name": "Hijack", "text": "x"}
        )
        assert response.status_code == 403
        project.refresh_from_db()
        assert project.name == "Theirs"

    def test_update_nonexistent_id_returns_404(self, auth_client):
        response = _post_json(auth_client, self.url, {"id": 9999, "name": "Ghost"})
        assert response.status_code == 404
        assert response.json() == {"error": "Project not found."}


class TestWheelPage:
    def test_wheel_page_renders_for_anonymous(self, client):
        response = client.get(reverse("dev-wheel"))
        assert response.status_code == 200
        assert response.context["wheel"] is None
        assert list(response.context["wheels"]) == []

    def test_wheel_page_lists_only_own_wheels(self, auth_client, user, other_user):
        mine = Wheel.objects.create(name="Mine", owner=user)
        Wheel.objects.create(name="Theirs", owner=other_user)
        response = auth_client.get(reverse("dev-wheel"))
        assert list(response.context["wheels"]) == [mine]


class TestWheelLoad:
    url = reverse("wheel-load")

    def test_anonymous_gets_401(self, client):
        response = client.get(self.url)
        assert response.status_code == 401
        assert response.json() == {"error": "Authentication required."}

    def test_no_wheel_id_resets_editor(self, auth_client):
        response = auth_client.get(self.url)
        assert response.status_code == 200
        assert response.context["wheel"] is None

    def test_load_own_wheel(self, auth_client, user):
        wheel = Wheel.objects.create(name="Mine", owner=user)
        item = WheelItem.objects.create(wheel=wheel, name="Option A")
        response = auth_client.get(self.url, {"wheel_id": wheel.id})
        assert response.status_code == 200
        assert response.context["wheel"] == wheel
        assert response.context["items"] == [{"id": item.id, "name": "Option A"}]

    def test_load_other_users_wheel_returns_403(self, auth_client, other_user):
        wheel = Wheel.objects.create(name="Theirs", owner=other_user)
        response = auth_client.get(self.url, {"wheel_id": wheel.id})
        assert response.status_code == 403
        assert response.json() == {"error": "You do not have permission to load this wheel."}

    def test_load_unknown_wheel_returns_404(self, auth_client):
        response = auth_client.get(self.url, {"wheel_id": 9999})
        assert response.status_code == 404


class TestWheelSave:
    url = reverse("wheel-save")

    def test_anonymous_gets_401(self, client):
        response = client.post(self.url, {"name": "Wheel", "items": "A\nB"})
        assert response.status_code == 401

    def test_blank_name_returns_400(self, auth_client):
        response = auth_client.post(self.url, {"name": "  ", "items": "A"})
        assert response.status_code == 400
        assert response.json() == {"error": "Wheel name is required."}

    def test_create_wheel_splits_items_on_newlines_dropping_blanks(self, auth_client, user):
        response = auth_client.post(
            self.url,
            {"name": "Dinner", "items": "  Pizza  \n\n   \nTacos\r\nSushi\n"},
        )
        assert response.status_code == 200
        wheel = Wheel.objects.get(name="Dinner", owner=user)
        # Lines are stripped and blank lines dropped.
        assert [i.name for i in wheel.items.order_by("id")] == ["Pizza", "Tacos", "Sushi"]
        assert response.context["wheel"] == wheel

    def test_save_replaces_existing_items_wholesale(self, auth_client, user):
        wheel = Wheel.objects.create(name="Old Name", owner=user)
        WheelItem.objects.create(wheel=wheel, name="Old A")
        WheelItem.objects.create(wheel=wheel, name="Old B")
        response = auth_client.post(
            self.url,
            {"wheel_id": wheel.id, "name": "New Name", "items": "New Only"},
        )
        assert response.status_code == 200
        wheel.refresh_from_db()
        assert wheel.name == "New Name"
        assert [i.name for i in wheel.items.all()] == ["New Only"]
        assert Wheel.objects.count() == 1

    def test_update_other_users_wheel_returns_403(self, auth_client, other_user):
        wheel = Wheel.objects.create(name="Theirs", owner=other_user)
        WheelItem.objects.create(wheel=wheel, name="Keep Me")
        response = auth_client.post(
            self.url, {"wheel_id": wheel.id, "name": "Hijack", "items": "X"}
        )
        assert response.status_code == 403
        wheel.refresh_from_db()
        assert wheel.name == "Theirs"
        assert [i.name for i in wheel.items.all()] == ["Keep Me"]


class TestWheelDelete:
    url = reverse("wheel-delete")

    def test_anonymous_gets_401(self, client, user):
        wheel = Wheel.objects.create(name="Mine", owner=user)
        response = client.post(self.url, {"wheel_id": wheel.id})
        assert response.status_code == 401
        assert Wheel.objects.filter(id=wheel.id).exists()

    def test_delete_own_wheel(self, auth_client, user):
        wheel = Wheel.objects.create(name="Mine", owner=user)
        WheelItem.objects.create(wheel=wheel, name="A")
        response = auth_client.post(self.url, {"wheel_id": wheel.id})
        assert response.status_code == 200
        assert not Wheel.objects.filter(id=wheel.id).exists()
        assert WheelItem.objects.count() == 0
        assert response.context["wheel"] is None

    def test_delete_other_users_wheel_returns_403(self, auth_client, other_user):
        wheel = Wheel.objects.create(name="Theirs", owner=other_user)
        response = auth_client.post(self.url, {"wheel_id": wheel.id})
        assert response.status_code == 403
        assert Wheel.objects.filter(id=wheel.id).exists()


class TestWheelItemDelete:
    def _url(self, item_id):
        return reverse("wheel-item-delete", kwargs={"item_id": item_id})

    def test_anonymous_gets_401(self, client, user):
        wheel = Wheel.objects.create(name="Mine", owner=user)
        item = WheelItem.objects.create(wheel=wheel, name="A")
        response = client.post(self._url(item.id))
        assert response.status_code == 401
        assert WheelItem.objects.filter(id=item.id).exists()

    def test_delete_own_item(self, auth_client, user):
        wheel = Wheel.objects.create(name="Mine", owner=user)
        item = WheelItem.objects.create(wheel=wheel, name="A")
        keep = WheelItem.objects.create(wheel=wheel, name="B")
        response = auth_client.post(self._url(item.id))
        assert response.status_code == 200
        assert not WheelItem.objects.filter(id=item.id).exists()
        assert WheelItem.objects.filter(id=keep.id).exists()
        assert response.context["wheel"] == wheel

    def test_delete_other_users_item_returns_403(self, auth_client, other_user):
        wheel = Wheel.objects.create(name="Theirs", owner=other_user)
        item = WheelItem.objects.create(wheel=wheel, name="A")
        response = auth_client.post(self._url(item.id))
        assert response.status_code == 403
        assert WheelItem.objects.filter(id=item.id).exists()

    def test_delete_unknown_item_returns_404(self, auth_client):
        response = auth_client.post(self._url(9999))
        assert response.status_code == 404
