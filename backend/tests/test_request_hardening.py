from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect

import backend.routes.game as game_routes
from backend.rate_limit import (
    MAX_WINDOW_SECONDS,
    SWEEP_EVERY_CHECKS,
    SlidingWindowRateLimiter,
    client_address,
)
from backend.request_limits import MAX_JSON_BODY_BYTES


def connection(peer: str, *forwarded: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_client_address_uses_socket_peer_without_trusted_proxies(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert client_address(connection("10.0.0.5", "203.0.113.9")) == "10.0.0.5"


def test_client_address_ignores_client_supplied_forwarded_entries(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    # The proxy appends the address it observed after anything the client sent.
    spoofed = connection("10.0.0.5", "198.51.100.1, 198.51.100.2, 203.0.113.9")
    assert client_address(spoofed) == "203.0.113.9"
    split_headers = connection("10.0.0.5", "198.51.100.1", "203.0.113.9")
    assert client_address(split_headers) == "203.0.113.9"

    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    assert client_address(connection("10.0.0.5", "203.0.113.9, 10.1.0.7")) == "203.0.113.9"
    # Fewer entries than trusted hops means the header cannot be relied on.
    assert client_address(connection("10.0.0.5", "203.0.113.9")) == "10.0.0.5"


def test_rate_limiter_discards_idle_keys(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    limiter = SlidingWindowRateLimiter()
    clock = [1000.0]
    monkeypatch.setattr("backend.rate_limit.time.monotonic", lambda: clock[0])
    for index in range(10):
        limiter.check(connection("10.0.0.1"), "bucket", limit=5, window_seconds=60,
                      discriminator=str(index))
    assert limiter.tracked_keys() == 10

    clock[0] += MAX_WINDOW_SECONDS + 1
    for _ in range(SWEEP_EVERY_CHECKS):
        limiter.check(connection("10.0.0.2"), "bucket", limit=10**6, window_seconds=60)
    assert limiter.tracked_keys() == 1


def test_oversized_json_bodies_are_rejected_with_cors_headers(client):
    origin = "http://localhost:5173"
    response = client.post(
        "/game/validate",
        content=b"{" + b" " * (MAX_JSON_BODY_BYTES + 1) + b"}",
        headers={"Content-Type": "application/json", "Origin": origin},
    )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == origin


def test_oversized_chunked_bodies_are_rejected(client):
    def chunks():
        yield b'{"rules": ['
        for _ in range(MAX_JSON_BODY_BYTES // 1024 + 2):
            yield b" " * 1024
        yield b"]}"

    response = client.post(
        "/game/validate",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_ordinary_requests_still_pass_the_size_limit(client):
    assert client.post("/game/validate", json={"mode": "local"}).status_code == 200


def test_custom_piece_patterns_are_bounded(client):
    piece = {
        "type": "blink",
        "displayName": "Blink",
        "symbols": {"white": "B", "black": "b"},
        "patterns": [{"dr": 1000, "dc": 0}],
    }
    response = client.post("/game/validate", json={"mode": "local", "customPieces": [piece]})
    assert response.status_code == 422

    piece["patterns"] = [{"dr": 1, "dc": 0, "mode": "teleport"}]
    response = client.post("/game/validate", json={"mode": "local", "customPieces": [piece]})
    assert response.status_code == 422


def test_websocket_must_authenticate_promptly(client, monkeypatch):
    monkeypatch.setattr(game_routes, "WEBSOCKET_AUTH_TIMEOUT_SECONDS", 0.05)
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    with client.websocket_connect(f"/game/ws/{game['id']}") as websocket:
        message = websocket.receive_json()
        assert message == {
            "type": "error",
            "message": "WebSocket authentication timed out",
            "status": 408,
        }
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
        assert closed.value.code == 1008


def test_websocket_connections_are_rate_limited(client):
    game = client.post("/game/create", json={"mode": "local"}).json()["game"]
    for _ in range(60):
        with client.websocket_connect(f"/game/ws/{game['id']}") as websocket:
            websocket.send_json({"type": "authenticate", "token": None})
            assert websocket.receive_json()["type"] == "game_state"
    with (
        pytest.raises(WebSocketDisconnect) as rejected,
        client.websocket_connect(f"/game/ws/{game['id']}"),
    ):
        pass
    assert rejected.value.code == 1008


def test_setup_endpoints_are_rate_limited_per_game(client):
    game_id = client.post("/game/create", json={"mode": "local"}).json()["game"]["id"]
    statuses = [
        client.post(f"/game/{game_id}/setup/handoff", json={}).status_code
        for _ in range(61)
    ]
    assert set(statuses[:60]) == {409}
    assert statuses[60] == 429


def test_diagnostics_show_how_client_addresses_resolve(client, monkeypatch):
    token = "test-only-diagnostics-token-32-characters"
    monkeypatch.setenv("DIAGNOSTICS_TOKEN", token)
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    response = client.get(
        "/internal/diagnostics",
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "1.2.3.4, 203.0.113.9"},
    )
    limiter = response.json()["rateLimiter"]
    assert limiter["trustedProxyHops"] == 1
    assert limiter["requestResolvedAs"] == "203.0.113.9"
    assert limiter["requestForwardedFor"] == "1.2.3.4, 203.0.113.9"


def test_game_state_responses_are_compressed(client):
    game = client.post(
        "/game/create",
        json={"mode": "local"},
        headers={"Accept-Encoding": "gzip"},
    )
    assert game.status_code == 200
    assert game.headers["content-encoding"] == "gzip"
    assert game.json()["game"]["id"]


def test_cors_allows_the_frontend_without_credentials(client):
    response = client.options(
        "/game/create",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers
