"""
File: test_mcu_graph.py
Description: MCU relationship graph: cytoscape renders on the page, the graph
and path APIs answer correctly, and the UI path search reports a found path.
Uses the `characters` fixture (Start Hero — Hub Hero — Finish Hero ally chain).
"""

from playwright.sync_api import Page, expect

GRAPH_URL = "/mcu-relationships/"


def test_graph_page_renders_canvas_without_js_errors(page: Page, live_server, characters):
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    page.goto(live_server.url + GRAPH_URL)

    # Cytoscape renders layered canvases inside #mcu-graph once /api/graph/ loads.
    expect(page.locator("#mcu-graph canvas").first).to_be_visible(timeout=20000)
    assert not console_errors, f"JS console errors on {GRAPH_URL}: {console_errors}"


def test_graph_api_returns_nodes_and_edges(page: Page, live_server, characters):
    response = page.request.get(live_server.url + "/api/graph/")

    assert response.status == 200
    data = response.json()
    assert "nodes" in data and "edges" in data
    node_labels = {node["data"].get("label") for node in data["nodes"]}
    assert {"Start Hero", "Hub Hero", "Finish Hero"} <= node_labels
    assert len(data["edges"]) == 2


def test_path_api_success_and_no_route(page: Page, live_server, characters):
    start = characters["start"]
    hub = characters["hub"]
    finish = characters["finish"]

    response = page.request.get(
        live_server.url + f"/api/graph/path/?from={start.id}&to={finish.id}"
    )
    assert response.status == 200
    payload = response.json()
    assert payload["character_ids"] == [start.id, hub.id, finish.id]
    assert str(hub.id) in payload["highlighted_nodes"]

    # An isolated character has no route to the chain.
    from connections.models import Character

    loner = Character.objects.create(name="Isolated Loner")
    no_route = page.request.get(
        live_server.url + f"/api/graph/path/?from={start.id}&to={loner.id}"
    )
    assert no_route.status == 404
    assert "error" in no_route.json()


def test_ui_path_search_finds_path(page: Page, live_server, characters):
    page.goto(live_server.url + GRAPH_URL)
    expect(page.locator("#mcu-graph canvas").first).to_be_visible(timeout=20000)

    page.locator("#path-from-dropdown summary").click()
    page.locator(
        '.graph-character-option[data-character-select="from"][data-character-name="Start Hero"]'
    ).click()

    page.locator("#path-to-dropdown summary").click()
    page.locator(
        '.graph-character-option[data-character-select="to"][data-character-name="Finish Hero"]'
    ).click()

    page.locator("#path-search-btn").click()

    status = page.locator("#path-status")
    expect(status).to_be_visible(timeout=15000)
    # graph.js: setStatus(`Path found with total traversal cost ${payload.total_cost}.`)
    expect(status).to_contain_text("Path found with total traversal cost")


def test_character_detail_api(page: Page, live_server, characters):
    start = characters["start"]

    response = page.request.get(live_server.url + f"/api/graph/character/{start.id}/")

    assert response.status == 200
    payload = response.json()
    assert payload["name"] == "Start Hero"
    assert payload["id"] == start.id
