"""Compare deployment predictions with the selected Torch model, not ground truth."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .data import read_manifest, resolve_image
from .inference import default_pipeline
from .onnx_inference import OnnxScannerPipeline


def verify(manifest_path, model_dir, limit, report_path):
    manifest = read_manifest(manifest_path)
    records = [record for record in manifest["records"] if record["split"] == "valid"][:limit]
    if not records:
        raise ValueError("No validation images are available.")
    reference, deployed = default_pipeline("cpu"), OnnxScannerPipeline(model_dir)
    maximum_score_error, maximum_box_error = 0, 0
    for index, record in enumerate(records):
        with Image.open(resolve_image(Path(manifest["dataset_root"]), record["file"])) as photo:
            image = photo.convert("RGB")
        expected = reference.predict(image, rectified=True)
        actual = deployed.predict(image, rectified=True)
        assert expected["board"] == actual["board"], f"Board mismatch: {record['id']}"
        assert expected["reviewSquares"] == actual["reviewSquares"], (
            f"Review mismatch: {record['id']}"
        )
        first, second = expected["prediction"], actual["prediction"]
        assert first["labels"] == second["labels"], f"Label mismatch: {record['id']}"
        for key, tolerance in (("boxes", 0.05), ("scores", 0.0001), ("classifier_scores", 0.002)):
            np.testing.assert_allclose(
                first[key], second[key], rtol=0, atol=tolerance, err_msg=f"{key}: {record['id']}"
            )
            difference = (
                float(np.max(np.abs(np.asarray(first[key]) - second[key]))) if first[key] else 0
            )
            if key == "boxes":
                maximum_box_error = max(maximum_box_error, difference)
            else:
                maximum_score_error = max(maximum_score_error, difference)
        assert [[choice["label"] for choice in options] for options in first["alternatives"]] == [
            [choice["label"] for choice in options] for options in second["alternatives"]
        ]
        print(f"Parity {index + 1}/{len(records)}", flush=True)
    report = {
        "images": len(records),
        "dataset_fingerprint": manifest["fingerprint"],
        "split": "valid",
        "image_ids": [record["id"] for record in records],
        "board_and_review_parity": True,
        "top_three_label_parity": True,
        "max_score_difference": maximum_score_error,
        "max_box_difference_pixels": maximum_box_error,
        "note": "Runtime parity only, not an independent accuracy benchmark.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json"),
    )
    parser.add_argument("--models", type=Path, default=Path("scanner/models/onnx"))
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--report", type=Path, default=Path("scanner/artifacts/onnx-parity.json"))
    args = parser.parse_args()
    verify(args.manifest, args.models, args.limit, args.report)
