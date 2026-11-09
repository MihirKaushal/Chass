"""Explain frozen detector errors by actual piece and predicted label."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .benchmark import METHOD, piece_diagnostics
from .data import CLASSES, read_manifest, save_json
from .metrics import box_iou

ERROR_METHOD = "class_agnostic_piece_errors_v1"
EXTRA_KINDS = ("duplicate_candidate", "localization_candidate", "background_candidate")


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def analyze(predictions, records, threshold):
    reference = piece_diagnostics(predictions, records, threshold)
    by_id = {p["image_id"]: p for p in predictions}
    actual = {name: Counter() for name in CLASSES[1:]}
    predicted = {name: Counter() for name in CLASSES[1:]}
    events, confusion = [], Counter()
    for record in records:
        gt = [
            (box, label)
            for box, label, crowd in zip(
                record["boxes"], record["labels"], record["iscrowd"], strict=True
            )
            if not crowd
        ]
        for _, label in gt:
            actual[CLASSES[label]]["support"] += 1
        p = by_id[record["id"]]
        detections = sorted(
            zip(p["boxes"], p["labels"], p["scores"], strict=True), key=lambda item: -item[2]
        )
        matched = set()
        for box, label, score in detections:
            if score < threshold:
                continue
            name = CLASSES[label]
            predicted[name]["predictions"] += 1
            overlaps = [(box_iou(box, b), i) for i, (b, _) in enumerate(gt)]
            overlap, index = max(
                (pair for pair in overlaps if pair[1] not in matched), default=(0, -1)
            )
            if overlap >= 0.5:
                matched.add(index)
                truth = CLASSES[gt[index][1]]
                actual[truth]["located"] += 1
                actual[truth]["correct"] += truth == name
                predicted[name]["correct"] += truth == name
                predicted[name]["wrong_label_on_real_piece"] += truth != name
                confusion[truth, name] += 1
                kind = "correct" if truth == name else "wrong_label"
            else:
                overlap, index = max(overlaps, default=(0, -1))
                truth = CLASSES[gt[index][1]] if index >= 0 else None
                kind = (
                    "duplicate_candidate"
                    if overlap >= 0.5
                    else "localization_candidate"
                    if overlap >= 0.1
                    else "background_candidate"
                )
                predicted[name][kind] += 1
            events.append(
                {
                    "image_id": record["id"],
                    "kind": kind,
                    "predicted": name,
                    "actual_or_nearest": truth,
                    "score": score,
                    "iou": overlap,
                    "box": box,
                    "target_box": gt[index][0] if index >= 0 else None,
                }
            )
        for index, (box, label) in enumerate(gt):
            if index not in matched:
                actual[CLASSES[label]]["missed"] += 1
                events.append(
                    {
                        "image_id": record["id"],
                        "kind": "missed",
                        "predicted": None,
                        "actual_or_nearest": CLASSES[label],
                        "target_box": box,
                    }
                )

    def actual_rows(counters):
        return [
            {
                "piece": name,
                **{k: c[k] for k in ("support", "located", "correct", "missed")},
                "miss_rate": rate(c["missed"], c["support"]),
                "conditional_type_color_accuracy": rate(c["correct"], c["located"]),
                "typed_piece_recall": rate(c["correct"], c["support"]),
            }
            for name, c in counters.items()
        ]

    by_type = {}
    for name, c in actual.items():
        by_type.setdefault(name.split("-")[1], Counter()).update(c)
    predicted_rows = []
    for name, c in predicted.items():
        unmatched = sum(c[k] for k in EXTRA_KINDS)
        incorrect = unmatched + c["wrong_label_on_real_piece"]
        predicted_rows.append(
            {
                "piece": name,
                **{
                    k: c[k]
                    for k in ("predictions", "correct", "wrong_label_on_real_piece", *EXTRA_KINDS)
                },
                "unmatched_predictions": unmatched,
                "incorrect_predictions": incorrect,
                "typed_prediction_precision": rate(c["correct"], c["predictions"]),
            }
        )
    totals = Counter(event["kind"] for event in events)
    # Guard against drift from the matching protocol used by the accuracy tracker.
    assert totals["correct"] == reference["correct_type_color"]
    assert totals["wrong_label"] + totals["correct"] == reference["localized_pieces"]
    assert totals["missed"] == reference["missed_pieces"]
    assert sum(totals[k] for k in EXTRA_KINDS) == reference["unmatched_predictions"]
    return {
        "matching_method": METHOD,
        "error_method": ERROR_METHOD,
        "images": len(records),
        "threshold": threshold,
        "matching_iou": 0.5,
        "background_iou_boundary": 0.1,
        "totals": {k: totals[k] for k in ("correct", "wrong_label", "missed", *EXTRA_KINDS)},
        "by_actual_class": actual_rows(actual),
        "by_actual_type": actual_rows(by_type),
        "by_predicted_class": predicted_rows,
        "confusions": [
            {"actual": a, "predicted": p, "count": n}
            for (a, p), n in sorted(confusion.items(), key=lambda item: (-item[1], item[0]))
        ],
    }, events


def write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--recorded-on", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--review", type=Path, help="Optional local directory for per-detection evidence."
    )
    args = parser.parse_args()
    if args.output.exists() or (args.review and args.review.exists()):
        parser.error("Choose new output/review directories to preserve existing analyses.")
    frozen = json.loads(args.snapshot.read_text())
    manifest = read_manifest(args.manifest)
    if manifest["fingerprint"] != frozen["dataset"]["fingerprint"]:
        parser.error("Snapshot and manifest fingerprints differ.")
    report = {
        "format_version": 1,
        "recorded_on": args.recorded_on.isoformat(),
        "run_id": frozen["run_id"],
        "training_date": frozen["training_date"],
        "checkpoint_sha256": frozen["checkpoint_sha256"],
        "dataset_fingerprint": manifest["fingerprint"],
        "parent_snapshot_sha256": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        "predictions_sha256": frozen["predictions_sha256"],
        "splits": {},
        "interpretation": [
            "Counts concern annotated boxes, not verified squares or physical piece identity.",
            "Duplicate candidates overlap an already matched annotation at IoU >= 0.5, regardless of class.",
            "Localization candidates have maximum IoU in [0.1, 0.5); background candidates have IoU < 0.1.",
            "These overlap buckets are diagnostics, not the full TIDE toolkit or proof that a piece is absent.",
            "Incorrect label predictions and duplicate predictions on real pieces are not background hallucinations.",
            "Type totals combine colors; report per-color support and small-sample uncertainty too.",
        ],
    }
    evidence = {}
    for split, frozen_values in frozen["splits"].items():
        path = args.artifacts / split / "predictions.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != frozen["predictions_sha256"][split]:
            parser.error(f"{split} predictions differ from the frozen snapshot.")
        records = [
            r
            for r in manifest["records"]
            if r["split"] == ("valid" if split == "validation" else split)
        ]
        result, events = analyze(
            json.loads(path.read_text()), records, frozen_values["detection"]["threshold"]
        )
        report["splits"][split] = result
        evidence[split] = events
    args.output.mkdir(parents=True)
    save_json(args.output / "analysis.json", report)
    for split, result in report["splits"].items():
        for key in ("by_actual_class", "by_actual_type", "by_predicted_class", "confusions"):
            write_csv(args.output / f"{split}-{key}.csv", result[key])
        if args.review:
            save_json(args.review / f"{split}-events.json", evidence[split])
    print(f"Saved piece error analysis to {args.output}")


if __name__ == "__main__":
    main()
