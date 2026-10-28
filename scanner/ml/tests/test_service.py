import io
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from scanner import service


def photo(format="PNG", size=(128, 128)):
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format=format)
    return output.getvalue()


class FakePipeline:
    def predict(self, image, *, rectified):
        assert rectified
        return {"board": [[None] * 8 for _ in range(8)], "reviewSquares": []}


def test_hosted_service_requires_secret_without_revealing_it(monkeypatch):
    monkeypatch.setenv("SCANNER_SERVICE_TOKEN", "private-test-token")
    with TestClient(service.create_app(FakePipeline())) as client:
        assert client.get("/ready").json() == {"ready": True}
        assert client.get("/health").status_code == 401
        response = client.post("/scan", content=photo(), headers={"content-type": "image/png"})
        assert response.status_code == 401 and "private-test-token" not in response.text
        headers = {"authorization": "Bearer private-test-token", "content-type": "image/png"}
        assert client.get("/health", headers=headers).json()["ready"]
        assert client.post("/scan", content=photo(), headers=headers).status_code == 200


def test_public_service_refuses_to_start_without_required_secret(monkeypatch):
    monkeypatch.setenv("SCANNER_REQUIRE_TOKEN", "true")
    monkeypatch.delenv("SCANNER_SERVICE_TOKEN", raising=False)
    with (
        pytest.raises(RuntimeError, match="SCANNER_SERVICE_TOKEN"),
        TestClient(service.create_app(FakePipeline())),
    ):
        pass


def test_local_service_returns_board_without_storing_photo():
    with TestClient(service.create_app(FakePipeline())) as client:
        assert client.get("/health").json() == {
            "ready": True,
            "experimental": True,
            "imagesStored": False,
        }
        response = client.post(
            "/scan",
            content=photo(),
            headers={"content-type": "image/png", "origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        assert response.json()["imageWidth"] == 128
        assert len(response.json()["imageSha256"]) == 64
        assert len(response.json()["board"]) == 8


def test_local_service_rejects_untrusted_origin_type_and_busy_work():
    app = service.create_app(FakePipeline())
    with TestClient(app) as client:
        assert (
            client.post(
                "/scan",
                content=photo(),
                headers={"content-type": "image/png", "origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        assert client.post("/scan", content=b"not a photo").status_code == 415
        app.state.busy = True
        assert (
            client.post("/scan", content=photo(), headers={"content-type": "image/png"}).status_code
            == 429
        )


def test_local_service_decode_failure_releases_worker(monkeypatch):
    app = service.create_app(FakePipeline())
    with TestClient(app) as client:
        headers = {"content-type": "image/png"}
        assert client.post("/scan", content=b"not an image", headers=headers).status_code == 422
        assert app.state.busy is False
        assert client.post("/scan", content=photo(), headers=headers).status_code == 200
        assert (
            client.post("/scan", content=photo(size=(256, 128)), headers=headers).status_code == 422
        )
        monkeypatch.setattr(service, "MAX_BYTES", 50)
        assert client.post("/scan", content=photo(), headers=headers).status_code == 413
        assert app.state.busy is False


def test_missing_models_and_inference_failure_are_explicit():
    class BrokenPipeline:
        def predict(self, *args, **kwargs):
            raise RuntimeError("Internal test failure")

    app = service.create_app(FakePipeline())
    with TestClient(app) as client:
        app.state.pipeline = None
        assert (
            client.post("/scan", content=photo(), headers={"content-type": "image/png"}).status_code
            == 503
        )
        app.state.pipeline = BrokenPipeline()
        response = client.post("/scan", content=photo(), headers={"content-type": "image/png"})
        assert response.status_code == 503
        assert "Internal test failure" not in response.text
        assert app.state.busy is False


def test_health_remains_responsive_and_second_inference_is_rejected():
    started, release = threading.Event(), threading.Event()

    class BlockingPipeline(FakePipeline):
        def predict(self, image, *, rectified):
            started.set()
            assert release.wait(5)
            return super().predict(image, rectified=rectified)

    with (
        TestClient(service.create_app(BlockingPipeline())) as client,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        pending = executor.submit(
            client.post, "/scan", content=photo(), headers={"content-type": "image/png"}
        )
        try:
            assert started.wait(5)
            assert client.get("/health").status_code == 200
            assert (
                client.post(
                    "/scan", content=photo(), headers={"content-type": "image/png"}
                ).status_code
                == 429
            )
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 200


def test_photo_size_format_and_decode_safety(monkeypatch):
    with pytest.raises(ValueError):
        service.decode_photo(photo(size=(40, 40)))
    with pytest.raises(ValueError):
        service.decode_photo(photo(format="GIF"))
    monkeypatch.setattr(service, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="pixel limit"):
        service.decode_photo(photo())


def test_photo_resizing_preserves_aspect():
    image = service.decode_photo(photo(size=(2400, 1200)))
    assert image.size == (2048, 1024)
