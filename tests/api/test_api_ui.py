"""Tests for the built UI served by the backend."""

import pytest
from fastapi.testclient import TestClient

from court_booker.api.app import create_app

PAGE = "<!doctype html><title>Court Booker</title>"


@pytest.fixture
def built(tmp_path):
    """A small built UI, with a file beside it that must stay out of reach."""
    folder = tmp_path / "built"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text(PAGE, encoding="utf-8")
    (folder / "assets" / "index-abc.js").write_text("export {};", encoding="utf-8")
    (folder / "assets" / "index-abc.css").write_text("body {}", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    return folder


@pytest.fixture
def ui_client(context, built):
    with TestClient(create_app(context, ui_folder=built)) as client:
        yield client


@pytest.mark.parametrize("address", ["/", "/history", "/some/old/address"])
def test_every_address_opens_the_ui(ui_client, address):
    response = ui_client.get(address)

    assert response.status_code == 200
    assert response.text == PAGE
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    ("address", "kind"),
    [("/assets/index-abc.js", "text/javascript"), ("/assets/index-abc.css", "text/css")],
)
def test_the_built_files_have_their_types(ui_client, address, kind):
    response = ui_client.get(address)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(kind)


def test_files_outside_the_build_stay_out_of_reach(ui_client):
    response = ui_client.get("/assets/..%2F..%2Fsecret.txt")

    assert response.text == PAGE


def test_the_api_wins_over_the_ui(ui_client):
    assert ui_client.get("/api/health").json()["status"] == "ok"
    assert "paths" in ui_client.get("/api/openapi.json").json()
    assert "swagger" in ui_client.get("/api/docs").text.lower()


@pytest.mark.parametrize("address", ["/api", "/api/nothing-here"])
def test_an_unknown_api_address_is_a_problem_not_the_ui(ui_client, address):
    response = ui_client.get(address)

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_the_live_feed_wins_over_the_ui(ui_client):
    with ui_client.websocket_connect("/api/live") as socket:
        socket.close()


def test_no_ui_is_served_without_a_folder(client):
    assert client.get("/").status_code == 404
    assert client.get("/history").status_code == 404
