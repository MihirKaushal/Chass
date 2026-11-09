"""Evaluate verified board labels, independently of detector-box benchmarks."""

import argparse
import hashlib
import json
import math
import statistics
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
        or record.get("verification") == "user_reviewed_not_independently_audited"
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
    metrics = square_metrics(
        [found[key]["board"] for key in expected], [expected[key]["board"] for key in expected]
    )
    board_reports, flagged, caught, false_flags, errors = [], 0, 0, 0, 0
    review_available = all("reviewSquares" in row for row in found.values())
    for key, record in expected.items():
        incorrect = {
            (r, c)
            for r in range(8)
            for c in range(8)
            if found[key]["board"][r][c] != record["board"][r][c]
        }
        review = found[key].get("reviewSquares", [])
        if any(
            not isinstance(s, dict)
            or type(s.get("row")) is not int
            or type(s.get("col")) is not int
            or not 0 <= s["row"] < 8
            or not 0 <= s["col"] < 8
            for s in review
        ):
            raise ValueError("Invalid review square.")
        targets = {(s["row"], s["col"]) for s in review}
        flagged += len(targets)
        errors += len(incorrect)
        caught += len(targets & incorrect)
        false_flags += len(targets - incorrect)
        board_reports.append(
            {
                "image_id": key,
                "corrections": len(incorrect),
                "incorrect_squares": [f"{'abcdefgh'[c]}{8 - r}" for r, c in sorted(incorrect)],
                "review_flags": len(targets) if review_available else None,
            }
        )
    metrics["review"] = {
        "measured": review_available,
        "flagged_squares": flagged if review_available else None,
        "errors_caught": caught if review_available else None,
        "unnecessary_flags": false_flags if review_available else None,
        "error_recall": caught / errors if review_available and errors else None,
        "flag_precision": caught / flagged if review_available and flagged else None,
    }
    metrics["per_board"] = board_reports
    # User review time is descriptive, not proof that the reviewed labels are correct.
    durations = [r.get("review", {}).get("active_ms") for r in expected.values()]
    durations = [
        t
        for t in durations
        if isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) and t >= 0
    ]
    metrics["review_time"] = {
        "samples": len(durations),
        "median_active_ms": statistics.median(durations) if durations else None,
    }
    return metrics


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
