"""Summarize frozen detections without inferring unverified chess squares."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

from .data import CLASSES, read_manifest, save_json
from .metrics import box_iou, operating_metrics

METHOD = "confidence_ordered_class_agnostic_iou_v1"


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def piece_diagnostics(predictions, records, threshold, matching_iou=0.5):
    """Match boxes before looking at their class; duplicates remain false alarms."""
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Confidence threshold must be between 0 and 1.")
    if not math.isfinite(matching_iou) or not 0 < matching_iou <= 1:
        raise ValueError("Matching IoU must be greater than 0 and at most 1.")
    by_id = {item["image_id"]: item for item in predictions}
    ids = {record["id"] for record in records}
    if len(by_id) != len(predictions) or len(ids) != len(records) or set(by_id) != ids:
        raise ValueError("Predictions must cover each evaluated image exactly once.")
    counts = Counter()
    confusions = Counter()
    for record in records:
        gt = [
            (box, label)
            for box, label, crowd in zip(
                record["boxes"], record["labels"], record["iscrowd"], strict=True
            )
            if not crowd
        ]
        counts["annotated_pieces"] += len(gt)
        prediction = by_id[record["id"]]
        detections = list(
            zip(prediction["boxes"], prediction["labels"], prediction["scores"], strict=True)
        )
        for box, label, score in detections:
            if (
                not math.isfinite(score)
                or not 0 <= score <= 1
                or not isinstance(label, int)
                or not 1 <= label < len(CLASSES)
                or len(box) != 4
                or not all(math.isfinite(value) for value in box)
                or box[2] <= box[0]
                or box[3] <= box[1]
            ):
                raise ValueError("Invalid piece detection.")
        matched = set()
        for box, label, score in sorted(detections, key=lambda item: -item[2]):
            if score < threshold:
                continue
            counts["predictions"] += 1
            overlap, index = max(
                (
                    (box_iou(box, target), index)
                    for index, (target, _) in enumerate(gt)
                    if index not in matched
                ),
                default=(0, -1),
            )
            if overlap < matching_iou:
                continue
            matched.add(index)
            counts["localized_pieces"] += 1
            actual, predicted = CLASSES[gt[index][1]], CLASSES[label]
            actual_color, actual_type = actual.split("-")
            predicted_color, predicted_type = predicted.split("-")
            counts["correct_type"] += actual_type == predicted_type
            counts["correct_color"] += actual_color == predicted_color
            counts["correct_type_color"] += actual == predicted
            confusions[actual, predicted] += 1
    gt_count, detected = counts["annotated_pieces"], counts["predictions"]
    localized, correct = counts["localized_pieces"], counts["correct_type_color"]
    return {
        "method": METHOD,
        "images": len(records),
        "threshold": threshold,
        "matching_iou": matching_iou,
        **{
            key: counts[key]
            for key in (
                "annotated_pieces",
                "predictions",
                "localized_pieces",
                "correct_type",
                "correct_color",
                "correct_type_color",
            )
        },
        "unmatched_predictions": detected - localized,
        "missed_pieces": gt_count - localized,
        "localization_precision": _ratio(localized, detected),
        "localization_recall": _ratio(localized, gt_count),
        "localization_f1": _ratio(2 * localized, detected + gt_count),
        "conditional_type_accuracy": _ratio(counts["correct_type"], localized),
        "conditional_color_accuracy": _ratio(counts["correct_color"], localized),
        "conditional_type_color_accuracy": _ratio(correct, localized),
        "typed_prediction_precision": _ratio(correct, detected),
        "typed_piece_recall": _ratio(correct, gt_count),
        "type_color_confusion": [
            {"actual": actual, "predicted": predicted, "count": count}
            for (actual, predicted), count in sorted(confusions.items())
        ],
        "square_metrics": {
            "occupancy_accuracy": None,
            "occupied_square_type_color_accuracy": None,
            "overall_13_class_square_accuracy": None,
            "exact_board_accuracy": None,
            "reason": "No verified 64-square labels, board geometry, or square-assigned predictions.",
        },
    }


def snapshot(results_path, manifest_path, artifacts, run_id, recorded_on):
    source = json.loads(results_path.read_text())
    manifest = read_manifest(manifest_path)
    fingerprint = manifest["fingerprint"]
    if source["dataset"]["fingerprint"] != fingerprint:
        raise ValueError("Results and manifest refer to different datasets.")
    if source["validation"]["threshold"] != source["test"]["threshold"]:
        raise ValueError("Test must use the frozen validation-selected threshold.")
    if source["validation"]["checkpoint_sha256"] != source["test"]["checkpoint_sha256"]:
        raise ValueError("Validation and test must evaluate the same checkpoint.")
    splits, prediction_hashes = {}, {}
    for key, split in (("validation", "valid"), ("test", "test")):
        metrics = source[key]
        if metrics["dataset_fingerprint"] != fingerprint:
            raise ValueError("Evaluation and manifest fingerprints differ.")
        prediction_path = artifacts / key / "predictions.json"
        predictions = json.loads(prediction_path.read_text())
        records = [item for item in manifest["records"] if item["split"] == split]
        diagnostic = piece_diagnostics(predictions, records, metrics["threshold"])
        checked = operating_metrics(predictions, records, metrics["threshold"])
        if any(checked[name] != metrics[name] for name in ("tp", "fp", "fn", "support", "images")):
            raise ValueError("Saved predictions do not reproduce the recorded detection counts.")
        splits[key] = {"detection": metrics, "piece_diagnostics": diagnostic}
        prediction_hashes[key] = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    return {
        "format_version": 1,
        "run_id": run_id,
        "training_date": source["run_date"],
        "recorded_on": recorded_on.isoformat(),
        "architecture": source["architecture"],
        "dataset": source["dataset"],
        "training": source["training"],
        "environment": source["environment"],
        "checkpoint_sha256": source["test"]["checkpoint_sha256"],
        "results_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
        "predictions_sha256": prediction_hashes,
        "splits": splits,
        "limitations": [
            "Box-level diagnostics, not square occupancy or whole-board accuracy.",
            "Unmatched predictions include duplicate labels/boxes, not just empty-square false alarms.",
            "Confidence-ordered matching ignores class until after localization; do not mix its counts with class-aware COCO counts.",
            "Undefined and unavailable values are null, not zero.",
            "Compare growth only on the same frozen dataset/split and method; never tune on test.",
        ],
    }


def export(snapshot_data, output):
    if output.suffix != ".json":
        raise ValueError("Snapshot output must have a .json extension.")
    csv_path = output.with_suffix(".csv")
    if output.exists() or csv_path.exists():
        raise ValueError("Benchmark snapshots are immutable; choose a new output filename.")
    rows = []
    for split, values in snapshot_data["splits"].items():
        diagnostic, detection = values["piece_diagnostics"], values["detection"]
        row = {
            key: snapshot_data[key]
            for key in (
                "run_id",
                "training_date",
                "recorded_on",
                "architecture",
                "checkpoint_sha256",
            )
        }
        row.update(
            dataset_fingerprint=snapshot_data["dataset"]["fingerprint"],
            split=split,
            train_images=snapshot_data["dataset"]["splits"]["train"]["images"],
            train_piece_boxes=snapshot_data["dataset"]["splits"]["train"]["annotations"],
            best_epoch=snapshot_data["training"]["best_epoch"],
        )
        row.update(
            {
                key: value
                for key, value in diagnostic.items()
                if key
                not in (
                    "type_color_confusion",
                    "square_metrics",
                )
            }
        )
        row.update(
            {key: value for key, value in diagnostic["square_metrics"].items() if key != "reason"}
        )
        row.update(
            {
                f"class_aware_{key}": detection[key]
                for key in (
                    "map50",
                    "map50_95",
                    "precision",
                    "recall",
                    "f1",
                    "exact_detection_image_rate",
                )
            }
        )
        rows.append(row)
    save_json(output, snapshot_data)
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--recorded-on", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = snapshot(
            args.results, args.manifest, args.artifacts, args.run_id, args.recorded_on
        )
        export(result, args.output)
    except ValueError as error:
        parser.exit(2, f"{error}\n")
    print(
        f"Saved {args.output} and {args.output.with_suffix('.csv')}; no inference or training run."
    )


if __name__ == "__main__":
    main()
