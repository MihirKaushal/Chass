"""Validation-only geometry and extra-review trials on verified prepared boards."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from .data import save_json
from .geometry import assign_squares
from .square_benchmark import evaluate


def remap(prediction, width, height, vertical_anchor):
    if vertical_anchor not in (0.5, 0.65, 0.8):
        raise ValueError("Use one of the predefined geometry candidates.")
    candidate = copy.deepcopy(prediction)
    # This is a heuristic probe, not an assertion that the bottom of a box is the base.
    for box in candidate["boxes"]:
        offset = (vertical_anchor - 0.5) * (box[3] - box[1])
        box[1] += offset
        box[3] += offset
    return assign_squares(candidate, width, height)


def extra_review(baseline, sensitive):
    result = copy.deepcopy(baseline)
    flagged = {(r["row"], r["col"]) for r in result["reviewSquares"]}
    for row in range(8):
        for col in range(8):
            if (
                baseline["board"][row][col] is None
                and sensitive["board"][row][col] is not None
                and (row, col) not in flagged
            ):
                result["reviewSquares"].append(
                    {
                        "row": row,
                        "col": col,
                        "reasons": [
                            "A lower-threshold detection suggests a possible missing piece"
                        ],
                    }
                )
    return result


def run(collection_path, photos, models, output):
    from PIL import Image

    from .onnx_inference import OnnxScannerPipeline

    if output.exists():
        raise ValueError("Use a fresh output path.")
    collection = json.loads(collection_path.read_text())
    records = [r for r in collection["records"] if r["split"] == "valid"]
    if not records or any(
        not r.get("verified") or r.get("orientation") != "white_bottom" for r in records
    ):
        raise ValueError("This experiment requires verified validation boards, never test images.")
    pipeline = OnnxScannerPipeline(models)
    rows = {"center_baseline": [], "anchor_065": [], "anchor_080": [], "extra_review_015": []}
    for record in records:
        photo = (photos / record["file"]).resolve()
        if (
            not photo.is_relative_to(photos.resolve())
            or hashlib.sha256(photo.read_bytes()).hexdigest() != record["image_sha256"]
        ):
            raise ValueError("Photo path or hash differs from the verified collection.")
        with Image.open(photo) as source:
            image = source.convert("RGB")
        baseline = pipeline.predict(image, rectified=True)
        threshold = pipeline.selection["threshold"]
        try:
            pipeline.selection["threshold"] = min(threshold, 0.15)
            sensitive = pipeline.predict(image, rectified=True)
        finally:
            pipeline.selection["threshold"] = threshold
        candidates = {
            "center_baseline": baseline,
            "anchor_065": remap(baseline["prediction"], *image.size, 0.65),
            "anchor_080": remap(baseline["prediction"], *image.size, 0.8),
            "extra_review_015": extra_review(baseline, sensitive),
        }
        for name, result in candidates.items():
            rows[name].append(
                {
                    "image_id": record["image_id"],
                    "image_sha256": record["image_sha256"],
                    "board": result["board"],
                    "reviewSquares": result["reviewSquares"],
                }
            )
    save_json(
        output,
        {
            "split": "valid",
            "promoted": False,
            "collection_sha256": hashlib.sha256(collection_path.read_bytes()).hexdigest(),
            "model_sha256": pipeline.config["sha256"],
            "candidates": {
                name: evaluate({"records": entries}, {"records": records})
                for name, entries in rows.items()
            },
            "limitations": [
                "Extra-review is a detector-threshold probe, not an independent occupancy model.",
                "Vertical anchors are heuristics; no physical base labels were learned.",
                "Production behavior is unchanged. A holdout and runtime check are required before promotion.",
            ],
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--models", type=Path, default=Path("scanner/models/onnx"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.collection, args.photos, args.models, args.output)
