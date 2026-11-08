from backend.observability import OperationalMetrics


def test_public_health_is_minimal(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_diagnostics_require_separate_secret(client, monkeypatch):
    monkeypatch.delenv("DIAGNOSTICS_TOKEN", raising=False)
    assert client.get("/internal/diagnostics").status_code == 404
    token = "test-only-diagnostics-token-32-characters"
    monkeypatch.setenv("DIAGNOSTICS_TOKEN", token)
    assert client.get("/internal/diagnostics").status_code == 401
    response = client.get("/internal/diagnostics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["botEngines"]["chass"] == "ready"
    assert token not in response.text
    assert response.json()["metrics"]["scope"] == "process_lifetime"


def test_metrics_have_bounded_labels_and_no_request_payloads():
    metrics = OperationalMetrics()
    metrics.record("scanner", "ok", 10)
    metrics.record("scanner", "error", 30)
    snapshot = metrics.snapshot()
    assert snapshot["counts"] == {"scanner.ok": 1, "scanner.error": 1}
    assert snapshot["latencyMs"]["scanner"] == {"count": 2, "mean": 20, "max": 30}


def test_failed_imports_are_counted_including_schema_rejections(client, monkeypatch):
    monkeypatch.setenv("DIAGNOSTICS_TOKEN", "x" * 32)
    headers = {"Authorization": "Bearer " + "x" * 32}
    before = (
        client.get("/internal/diagnostics", headers=headers)
        .json()["metrics"]["counts"]
        .get("import.error", 0)
    )
    assert client.post("/game/import", json={}).status_code == 422
    after = client.get("/internal/diagnostics", headers=headers).json()["metrics"]["counts"][
        "import.error"
    ]
    assert after == before + 1
