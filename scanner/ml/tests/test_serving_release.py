import hashlib
import json
from pathlib import Path

from scanner.ml.serving_paths import model_paths

ROOT = Path(__file__).resolve().parents[3]


def test_serving_release_matches_verified_candidate():
    manifest = json.loads((ROOT / "scanner/models/onnx/manifest.json").read_text())
    benchmark = ROOT / "scanner/ml/benchmarks/merged-data-2026-11-08"
    result = json.loads((benchmark / "results.json").read_text())
    assert result["decision"]["accuracy_gate_passed"]
    assert manifest["selection"] == result["selections"]["merged"]
    assert json.loads((benchmark / "onnx-parity.json").read_text())["board_and_review_parity"]
    for stage in ("detector", "classifier"):
        digest = hashlib.sha256((ROOT / f"scanner/models/onnx/{stage}.onnx").read_bytes()).hexdigest()
        assert digest == manifest["sha256"][stage]
    baseline = json.loads((benchmark / "baseline-onnx-manifest.json").read_text())
    for stage in ("detector", "classifier"):
        assert baseline["selection"][f"{stage}_sha256"] == result["protocol"]["initialization"][stage]["sha256"]


def test_default_torch_paths_and_environment_overrides(monkeypatch):
    names = ("SCANNER_SELECTION", "SCANNER_DETECTOR", "SCANNER_CLASSIFIER")
    for name in names:
        monkeypatch.delenv(name, raising=False)
    selection, detector, classifier = model_paths()
    assert str(selection).endswith("merge-evaluation-2026-11-08/merged/selection.json")
    assert str(detector).endswith("merge-experiment-2026-11-08/merged/detector/best.pt")
    assert str(classifier).endswith("merge-experiment-2026-11-08/merged/classifier/best.pt")
    for name in names:
        monkeypatch.setenv(name, f"/custom/{name}")
    assert model_paths() == tuple(Path(f"/custom/{name}") for name in names)
