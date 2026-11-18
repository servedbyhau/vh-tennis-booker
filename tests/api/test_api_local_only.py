"""The backend refuses requests that a page of another site makes the browser send."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from court_booker.api.local_only import is_local_host, is_local_origin


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "127.0.0.1", "localhost:8765", "LOCALHOST"])
def test_this_pc_is_a_local_host(host):
    assert is_local_host(host)  # the desktop window's health check sends "127.0.0.1" alone


@pytest.mark.parametrize(
    "host", ["evil.example:8765", "evil.example", "", "127.0.0.1.evil.example"]
)
def test_another_name_is_not(host):
    assert not is_local_host(host)


@pytest.mark.parametrize(
    "origin", ["http://127.0.0.1:8765", "http://localhost:5173", "http://127.0.0.1:5173"]
)
def test_pages_of_this_pc_are_local(origin):
    assert is_local_origin(origin)  # the packaged window, and Vite in development


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "http://evil.example:8765", "null", "file://", ""]
)
def test_other_pages_are_not(origin):
    assert not is_local_origin(origin)


def test_a_request_from_the_app_s_own_page_goes_through(client):
    reply = client.get("/api/health", headers={"Origin": "http://127.0.0.1:8765"})

    assert reply.status_code == 200


def test_a_request_without_a_page_goes_through(client):
    assert client.get("/api/health").status_code == 200  # a command line sends no Origin


def test_a_post_from_another_site_starts_nothing(client, monkeypatch):
    from court_booker.api import runs

    started = []
    monkeypatch.setattr(runs, "start_dry_run", lambda *args: started.append(args))

    reply = client.post("/api/runs/dry-run", headers={"Origin": "https://evil.example"})

    assert reply.status_code == 403
    assert reply.json()["error"] == "forbidden"
    assert started == []


def test_a_name_pointed_at_this_pc_is_refused(app):
    with TestClient(app, base_url="http://evil.example:8765") as client:
        reply = client.get("/api/settings")

    assert reply.status_code == 403
    assert "evil.example" in reply.json()["detail"]


LIVE = "ws://127.0.0.1:8765/api/live"
"""The live feed in full: the test client sends a WebSocket to "testserver" otherwise."""


def test_the_live_feed_refuses_another_site(client):
    evil = {"Origin": "https://evil.example"}
    disconnected = pytest.raises(WebSocketDisconnect)
    with disconnected as refused, client.websocket_connect(LIVE, headers=evil):
        pass

    assert refused.value.code == 1008


def test_the_live_feed_accepts_the_app_s_page(client):
    with client.websocket_connect(LIVE, headers={"Origin": "http://127.0.0.1:8765"}):
        pass  # accepted: a refused handshake raises WebSocketDisconnect
