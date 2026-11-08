"""Isolated browser-test servers: temporary SQLite and the real scanner HTTP wrapper.

Only model inference is replaced by a deterministic fixture; no production resources.
"""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FixturePipeline:
    def predict(self, image, *, rectified):
        return json.loads((ROOT / "backend/tests/fixtures/scanner-response.json").read_text())


def main():
    with tempfile.TemporaryDirectory(prefix="chass-e2e-") as directory:
        os.environ.update(
            {
                "ENVIRONMENT": "development",
                "PERSISTENCE_BACKEND": "sql",
                "DATABASE_URL": f"sqlite:///{directory}/games.db",
                "FRONTEND_URL": "http://127.0.0.1:14173",
                "ALLOWED_ORIGINS": "http://127.0.0.1:14173",
                "TOKEN_SECRET": "isolated-e2e-token-not-used-in-production",
                "MATCH_PREDICTOR_ENGINE_ENABLED": "false",
                "SCANNER_SERVICE_URL": "http://127.0.0.1:18101",
                "SCANNER_SERVICE_TOKEN": "isolated-e2e-scanner-token",
                "SCANNER_REQUIRE_TOKEN": "true",
            }
        )
        from backend.main import app
        from scanner.service import create_app

        scanner = uvicorn.Server(
            uvicorn.Config(
                create_app(FixturePipeline()), host="127.0.0.1", port=18101, log_level="warning"
            )
        )
        thread = threading.Thread(target=scanner.run, daemon=True)
        thread.start()
        try:
            uvicorn.run(app, host="127.0.0.1", port=18100, log_level="warning")
        finally:
            scanner.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
