import httpx
import pytest

from backend.routes import scanner


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setenv("SCANNER_SERVICE_URL", "https://model.example")
    monkeypatch.setenv("SCANNER_SERVICE_TOKEN", "secret-test-token")
    monkeypatch.setattr(
        scanner.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_gateway_keeps_private_token_server_side_and_forwards_only_photo(client, monkeypatch):
    def handler(request):
        assert request.headers["authorization"] == "Bearer secret-test-token"
        assert "origin" not in request.headers
        if request.url.path == "/health":
            return httpx.Response(200, json={"ready": True})
        assert request.content == b"test-photo"
        return httpx.Response(
            200, json={"board": [[None] * 8 for _ in range(8)], "reviewSquares": []}
        )

    transport(monkeypatch, handler)
    assert client.get("/scanner/health").json()["ready"]
    response = client.post(
        "/scanner/scan", content=b"test-photo", headers={"Content-Type": "image/jpeg"}
    )
    assert response.status_code == 200 and "secret-test-token" not in response.text


def test_gateway_handles_offline_bad_config_format_and_size(client, monkeypatch):
    monkeypatch.setenv("SCANNER_SERVICE_URL", "")
    assert client.get("/scanner/health").json() == {"ready": False, "configured": False}
    assert client.post("/scanner/scan").status_code == 503
    monkeypatch.setenv("SCANNER_SERVICE_URL", "https://model.example")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SCANNER_SERVICE_TOKEN", raising=False)
    assert client.get("/scanner/health").status_code == 503
    monkeypatch.setenv("SCANNER_SERVICE_TOKEN", "test")
    assert client.post("/scanner/scan", content=b"bad").status_code == 415
    monkeypatch.setattr(scanner, "MAX_BYTES", 2)
    assert (
        client.post(
            "/scanner/scan", content=b"too large", headers={"Content-Type": "image/jpeg"}
        ).status_code
        == 413
    )


@pytest.mark.parametrize("status,expected", [(401, 503), (429, 429), (422, 422), (302, 503)])
def test_gateway_does_not_leak_upstream_auth_errors_or_follow_redirects(
    client, monkeypatch, status, expected
):
    transport(
        monkeypatch,
        lambda request: httpx.Response(
            status, json={"detail": "test"}, headers={"Location": "https://other.example"}
        ),
    )
    response = client.post("/scanner/scan", content=b"photo", headers={"Content-Type": "image/png"})
    assert response.status_code == expected


def test_gateway_timeout_does_not_impact_games(client, monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("timeout")

    transport(monkeypatch, handler)
    health = client.get("/scanner/health").json()
    assert not health["ready"] and health["status"] == "warming"
    assert (
        client.post(
            "/scanner/scan", content=b"photo", headers={"Content-Type": "image/png"}
        ).status_code
        == 504
    )
    assert client.post("/game/create", json={"mode": "local"}).status_code == 200


@pytest.mark.parametrize("kind", ["html", "http-error", "not-ready"])
def test_health_handles_cold_host_response_then_recovers(client, monkeypatch, kind):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls > 1:
            return httpx.Response(200, json={"ready": True})
        if kind == "html":
            return httpx.Response(200, text="<html>Starting your service</html>")
        if kind == "http-error":
            return httpx.Response(503)
        return httpx.Response(200, json={"ready": False})

    transport(monkeypatch, handler)
    first = client.get("/scanner/health").json()
    assert first["status"] == "warming" and not first["ready"]
    second = client.get("/scanner/health").json()
    assert second["status"] == "ready" and second["ready"]


@pytest.mark.parametrize("code", [401, 403, 404])
def test_health_marks_configuration_failures_without_exposing_service_details(client, monkeypatch, code):
    transport(monkeypatch, lambda request: httpx.Response(code, text="private upstream details"))
    response = client.get("/scanner/health")
    assert response.json() == {"ready": False, "configured": True, "status": "unavailable"}
    assert "private upstream" not in response.text
    assert "secret-test-token" not in response.text
