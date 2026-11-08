import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.models.scanner import ScanResponse
from backend.tests.test_scanner_gateway import transport
from scanner.service import create_app

FIXTURE = Path(__file__).parent / "fixtures/scanner-response.json"


def response_data():
    return json.loads(FIXTURE.read_text())


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update(board=[]),
        lambda data: data["board"][0].pop(),
        lambda data: data["board"][0].__setitem__(0, "white-elephant"),
        lambda data: data["reviewSquares"][0].update(row=8),
        lambda data: data["reviewSquares"][0].update(col=True),
        lambda data: data["reviewSquares"][0].update(label="a1"),
        lambda data: data["reviewSquares"].append(copy.deepcopy(data["reviewSquares"][0])),
        lambda data: data.update(warnings=[{}]),
        lambda data: data["squareCandidates"][0].update(candidates="wrong"),
        lambda data: data["squareCandidates"][0]["candidates"][0].update(score=1.1),
        lambda data: data["squareCandidates"][0]["candidates"][0]["alternatives"][0].update(
            score="0.8"
        ),
        lambda data: data.update(imageWidth=-1),
        lambda data: data.update(privateToken="must-not-leak"),
        lambda data: data["prediction"].update(duplicate_counts=[]),
        lambda data: data["prediction"].update(duplicate_counts=[-1]),
    ],
)
def test_gateway_rejects_malformed_contract(client, monkeypatch, mutation):
    data = response_data()
    mutation(data)
    transport(monkeypatch, lambda request: httpx.Response(200, json=data))
    result = client.post("/scanner/scan", content=b"photo", headers={"Content-Type": "image/png"})
    assert result.status_code == 502
    assert "must-not-leak" not in result.text


def test_gateway_rejects_non_json_success(client, monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(200, text="not-json"))
    assert (
        client.post(
            "/scanner/scan", content=b"photo", headers={"Content-Type": "image/png"}
        ).status_code
        == 502
    )


def test_real_scanner_http_contract_round_trips_through_gateway(client, monkeypatch):
    class Pipeline:
        def predict(self, image, rectified):
            assert rectified and image.size == (512, 512)
            data = response_data()
            data["prediction"]["duplicate_counts"] = [1] * len(data["prediction"]["boxes"])
            return data

    monkeypatch.delenv("SCANNER_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("SCANNER_REQUIRE_TOKEN", raising=False)
    with TestClient(create_app(Pipeline())) as scanner_client:
        photo = (FIXTURE.parent / "board.png").read_bytes()
        upstream = scanner_client.post(
            "/scan", content=photo, headers={"Content-Type": "image/png"}
        )
        assert upstream.status_code == 200
        validated = ScanResponse.model_validate(upstream.json())
        assert validated.imageWidth == 512
        transport(monkeypatch, lambda request: httpx.Response(200, json=upstream.json()))
        result = client.post("/scanner/scan", content=photo, headers={"Content-Type": "image/png"})
        assert result.status_code == 200
        assert result.json() == upstream.json()
