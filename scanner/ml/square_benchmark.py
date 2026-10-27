"""Evaluate verified board labels, independently of detector-box benchmarks."""

import argparse
import hashlib
import json
from pathlib import Path

from .data import save_json
from .geometry import square_metrics


def evaluate(predictions, annotations):
    expected = {record["image_id"]: record for record in annotations["records"]}
    found = {record["image_id"]: record for record in predictions["records"]}
    if (
        len(expected) != len(annotations["records"])
        or len(found) != len(predictions["records"])
        or set(expected) != set(found)
    ):
        raise ValueError("Predictions must cover every verified image exactly once.")
    if any(
        record.get("verified") is not True
        or not record.get("image_sha256")
        or record.get("orientation") != "white_bottom"
        for record in expected.values()
    ):
        raise ValueError(
            "Ground truth requires verified labels, image hashes and White-at-bottom orientation."
        )
    if any(
        found[key].get("image_sha256") != record["image_sha256"] for key, record in expected.items()
    ):
        raise ValueError("Prediction and ground-truth photo hashes differ.")
    return square_metrics(
        [found[key]["board"] for key in expected], [expected[key]["board"] for key in expected]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new report path.")
    result = evaluate(
        json.loads(args.predictions.read_text()), json.loads(args.annotations.read_text())
    )
    result["annotations_sha256"] = hashlib.sha256(args.annotations.read_bytes()).hexdigest()
    result["predictions_sha256"] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    save_json(args.output, result)
