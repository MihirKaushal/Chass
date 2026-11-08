"""Exercise real ONNX weights and the scanner HTTP wrapper against the API contract.

The generated fixture tests integration, not recognition accuracy. No photos leave this process.
"""

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.models.scanner import ScanResponse  # noqa: E402
from scanner.ml.onnx_inference import default_pipeline  # noqa: E402
from scanner.service import create_app  # noqa: E402


def smoke():
    os.environ["SCANNER_SERVICE_TOKEN"] = "isolated-contract-smoke-token"
    with TestClient(create_app(default_pipeline())) as client:
        response = client.post(
            "/scan",
            content=(ROOT / "backend/tests/fixtures/board.png").read_bytes(),
            headers={
                "Content-Type": "image/png",
                "Authorization": "Bearer isolated-contract-smoke-token",
            },
        )
        response.raise_for_status()
        result = ScanResponse.model_validate(response.json())
        assert result.runtime == "onnx" and result.prediction is not None
        return {
            "status": "passed",
            "runtime": result.runtime,
            "detections": len(result.prediction.boxes),
            "inferenceMs": result.inferenceMs,
            "note": "Contract smoke only; synthetic input is not an accuracy benchmark.",
        }


if __name__ == "__main__":
    print(json.dumps(smoke(), indent=2))
