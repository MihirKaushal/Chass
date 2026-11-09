"""Validation-only King/recall selection with a locked decision before optional test evaluation."""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from .benchmark import piece_diagnostics
from .classifier import load_classifier
from .data import read_manifest, save_json
from .experiment import classify_predictions
from .model import choose_device
from .postprocess import resolve_duplicates


def summarize(predictions, records, threshold):
    metrics = piece_diagnostics(predictions, records, threshold)
    result = {
        key: metrics[key]
        for key in (
            "typed_piece_recall",
            "typed_prediction_precision",
            "conditional_type_color_accuracy",
            "missed_pieces",
            "unmatched_predictions",
            "localized_pieces",
            "correct_type_color",
            "annotated_pieces",
            "predictions",
        )
    }
    result["typed_f1"] = (
        2 * metrics["correct_type_color"] / (metrics["annotated_pieces"] + metrics["predictions"])
    )
    for color in ("black", "white"):
        name = f"{color}-king"
        entries = [r for r in metrics["type_color_confusion"] if r["actual"] == name]
        located = sum(r["count"] for r in entries)
        correct = sum(r["count"] for r in entries if r["predicted"] == name)
        result[f"{color}_king_accuracy"] = correct / located if located else 0
    return result


def passes(candidate, baseline):
    return (
        candidate["typed_piece_recall"] >= baseline["typed_piece_recall"]
        and candidate["typed_prediction_precision"]
        >= baseline["typed_prediction_precision"] - 0.005
        and candidate["typed_f1"] >= baseline["typed_f1"]
        and all(
            candidate[f"{c}_king_accuracy"] >= baseline[f"{c}_king_accuracy"] - 0.005
            for c in ("black", "white")
        )
    )


def run(manifest_path, detector_artifacts, checkpoints, output, test=False):
    if output.exists():
        raise ValueError("Use a fresh experiment directory.")
    output.mkdir(parents=True)
    manifest = read_manifest(manifest_path)
    metadata = json.loads((detector_artifacts / "validation/metrics.json").read_text())
    if metadata["dataset_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("Detector predictions and manifest differ.")
    records = [r for r in manifest["records"] if r["split"] == "valid"]
    original = json.loads((detector_artifacts / "validation/predictions.json").read_text())
    device = choose_device()
    torch.set_num_threads(4)
    rows = []
    for checkpoint_path in checkpoints:
        model, checkpoint = load_classifier(checkpoint_path, device)
        if checkpoint["dataset_fingerprint"] != manifest["fingerprint"]:
            raise ValueError("Classifier dataset differs.")
        classified = classify_predictions(
            model, checkpoint, manifest, records, original, device, threshold=0.15
        )
        for threshold in (0.15, 0.20, 0.25):
            for overlap in (0.4, 0.5, 0.6):
                predictions = [
                    resolve_duplicates(p, threshold=threshold, overlap=overlap) for p in classified
                ]
                rows.append(
                    {
                        "checkpoint": str(checkpoint_path),
                        "threshold": threshold,
                        "overlap": overlap,
                        "metrics": summarize(predictions, records, threshold),
                    }
                )
        save_json(output / f"{checkpoint_path.parent.name}-valid.json", classified)
        del model
    baseline = next(
        row
        for row in rows
        if row["checkpoint"] == str(checkpoints[0])
        and row["threshold"] == 0.25
        and row["overlap"] == 0.4
    )
    for row in rows:
        row["passes_gates"] = passes(row["metrics"], baseline["metrics"])
    selected = max((r for r in rows if r["passes_gates"]), key=lambda r: r["metrics"]["typed_f1"])
    selection = {
        **selected,
        "dataset_fingerprint": manifest["fingerprint"],
        "classifier_sha256": hashlib.sha256(Path(selected["checkpoint"]).read_bytes()).hexdigest(),
        "selection_split": "valid",
        "test_used_for_selection": False,
        "promoted": False,
        "reason": "Requires independent set and deployment memory/runtime checks.",
    }
    save_json(output / "selection.json", selection)
    save_json(output / "validation.json", {"baseline": baseline, "candidates": rows})
    print(json.dumps(selection), flush=True)
    if test:
        # Selection has already been written. Test results may veto, never choose a runner-up.
        records = [r for r in manifest["records"] if r["split"] == "test"]
        original = json.loads((detector_artifacts / "test/predictions.json").read_text())
        model, checkpoint = load_classifier(Path(selected["checkpoint"]), device)
        classified = classify_predictions(
            model, checkpoint, manifest, records, original, device, threshold=selected["threshold"]
        )
        predictions = [
            resolve_duplicates(p, threshold=selected["threshold"], overlap=selected["overlap"])
            for p in classified
        ]
        save_json(
            output / "test.json",
            {
                "selection": selection,
                "metrics": summarize(predictions, records, selected["threshold"]),
            },
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json"),
    )
    parser.add_argument(
        "--detector-artifacts", type=Path, default=Path("scanner/artifacts/chess-v2-baseline")
    )
    parser.add_argument("--checkpoints", type=Path, nargs="+", required=True, help="Baseline first")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    run(args.manifest, args.detector_artifacts, args.checkpoints, args.output, args.test)
