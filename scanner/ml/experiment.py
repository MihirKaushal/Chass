"""Validation-selected ablation of duplicate suppression and crop classification."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from PIL import Image

from .benchmark import piece_diagnostics
from .classifier import crop_transform, load_classifier
from .crops import piece_crop
from .data import CLASSES, read_manifest, resolve_image, save_json
from .model import choose_device
from .postprocess import resolve_duplicates


@torch.inference_mode()
def classify_predictions(model, checkpoint, manifest, records, predictions, device, threshold=0.25):
    by_id = {record["id"]: record for record in records}
    if set(by_id) != {prediction["image_id"] for prediction in predictions}:
        raise ValueError("Predictions and split records differ.")
    transform, results = crop_transform(), []
    config = checkpoint["config"]
    for number, prediction in enumerate(predictions):
        selected = [i for i, score in enumerate(prediction["scores"]) if score >= threshold]
        result = {
            "image_id": prediction["image_id"],
            "boxes": [],
            "scores": [],
            "labels": [],
            "detector_labels": [],
            "classifier_scores": [],
            "alternatives": [],
        }
        record = by_id[prediction["image_id"]]
        with Image.open(resolve_image(Path(manifest["dataset_root"]), record["file"])) as original:
            image = original.convert("RGB")
            for offset in range(0, len(selected), 48):
                indices = selected[offset : offset + 48]
                crops = [
                    transform(
                        piece_crop(
                            image,
                            prediction["boxes"][i],
                            context=config["context"],
                            size=config["size"],
                        )
                    )
                    for i in indices
                ]
                probabilities = model(torch.stack(crops).to(device)).softmax(1).cpu()
                values, classes = probabilities.topk(3, dim=1)
                for i, scores, labels in zip(
                    indices, values.tolist(), classes.tolist(), strict=True
                ):
                    result["boxes"].append(prediction["boxes"][i])
                    # Preserve proposal confidence/order to isolate the classifier's contribution.
                    result["scores"].append(prediction["scores"][i])
                    result["labels"].append(labels[0] + 1)
                    result["detector_labels"].append(prediction["labels"][i])
                    result["classifier_scores"].append(scores[0])
                    result["alternatives"].append(
                        [
                            {"label": CLASSES[label + 1], "score": score}
                            for label, score in zip(labels, scores, strict=True)
                        ]
                    )
        results.append(result)
        if number % 50 == 0:
            print(f"Reclassified {number + 1}/{len(predictions)} images", flush=True)
    return results


def select_overlap(predictions, records, threshold=0.25):
    baseline = piece_diagnostics(predictions, records, threshold)
    sweep = []
    for overlap in (0.4, 0.5, 0.6, 0.7, 0.8):
        metrics = piece_diagnostics(
            [resolve_duplicates(p, threshold=threshold, overlap=overlap) for p in predictions],
            records,
            threshold,
        )
        sweep.append({"overlap": overlap, "metrics": metrics})
    # Reject a cleaner-looking result if it loses more than 1% of localized validation pieces.
    eligible = [
        row
        for row in sweep
        if row["metrics"]["localized_pieces"] >= 0.99 * baseline["localized_pieces"]
    ]
    if not eligible:
        raise ValueError("No duplicate setting passes the validation localization recall gate.")
    best = max(eligible, key=lambda row: (row["metrics"]["localization_f1"], row["overlap"]))
    return best["overlap"], sweep


def run(manifest_path, artifacts, checkpoint_path, output, device_name="auto"):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new experiment directory to preserve earlier results.")
    output.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(manifest_path)
    device = choose_device(device_name)
    torch.set_num_threads(4)
    model, checkpoint = load_classifier(checkpoint_path, device)
    if checkpoint["dataset_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("Classifier and evaluated dataset fingerprints differ.")
    valid_records = [r for r in manifest["records"] if r["split"] == "valid"]
    valid_path = artifacts / "validation/predictions.json"
    validation = json.loads(valid_path.read_text())
    detector_metrics = json.loads((artifacts / "validation/metrics.json").read_text())
    if detector_metrics["dataset_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("Detector predictions and classifier refer to different datasets.")
    overlap, sweep = select_overlap(validation, valid_records)
    save_json(output / "duplicate-sweep.json", sweep)
    result = {
        "format_version": 1,
        "dataset_fingerprint": manifest["fingerprint"],
        "classifier_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
        "classifier_epoch": checkpoint["epoch"],
        "detector_sha256": detector_metrics["checkpoint_sha256"],
        "threshold": 0.25,
        "overlap": overlap,
        "selection": "Validation localization F1 with >=99% baseline localization recall; "
        "pipeline selected by validation typed F1. No test tuning.",
        "square_metrics": None,
        "splits": {},
    }
    for split, directory in (("valid", "validation"), ("test", "test")):
        records = [r for r in manifest["records"] if r["split"] == split]
        path = artifacts / directory / "predictions.json"
        original = json.loads(path.read_text())
        started = time.perf_counter()
        classified = classify_predictions(model, checkpoint, manifest, records, original, device)
        variants = {
            "baseline": original,
            "duplicates_only": [resolve_duplicates(p, overlap=overlap) for p in original],
            "classifier_only": classified,
            "combined": [resolve_duplicates(p, overlap=overlap) for p in classified],
        }
        result["splits"][split] = {
            "source_predictions_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "classification_seconds": time.perf_counter() - started,
            "variants": {
                name: piece_diagnostics(predictions, records, 0.25)
                for name, predictions in variants.items()
            },
        }
        if split == "valid":

            def typed_f1(name):
                metrics = result["splits"]["valid"]["variants"][name]
                return (
                    2
                    * metrics["correct_type_color"]
                    / (metrics["annotated_pieces"] + metrics["predictions"])
                )

            result["selected_pipeline"] = max(variants, key=typed_f1)
            # Persist the choice before reading test results.
            save_json(
                output / "selection.json",
                {
                    "pipeline": result["selected_pipeline"],
                    "overlap": overlap,
                    "threshold": 0.25,
                    "classifier_sha256": result["classifier_sha256"],
                    "detector_sha256": result["detector_sha256"],
                    "dataset_fingerprint": manifest["fingerprint"],
                },
            )
        for name in ("classifier_only", "combined"):
            save_json(output / f"{split}-{name}-predictions.json", variants[name])
        save_json(output / "results.json", result)
        print(
            json.dumps(
                {
                    "split": split,
                    "selected": result["selected_pipeline"],
                    "variants": {
                        name: {
                            k: metrics[k]
                            for k in (
                                "conditional_type_color_accuracy",
                                "typed_piece_recall",
                                "unmatched_predictions",
                                "missed_pieces",
                            )
                        }
                        for name, metrics in result["splits"][split]["variants"].items()
                    },
                }
            ),
            flush=True,
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="auto", choices=("auto", "mps", "cpu", "cuda"))
    args = parser.parse_args()
    run(args.manifest, args.artifacts, args.checkpoint, args.output, args.device)
