"""Equal-budget continuation experiment; never changes deployed scanner artifacts."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from .data import read_manifest, save_json

BASE = Path("scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json")
DETECTOR = Path("scanner/artifacts/chess-v2-baseline/best.pt")
CLASSIFIER = Path("scanner/artifacts/king-focused-2026-11-06/best.pt")


def prepare_experiment(merged, output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new experiment directory; preserve earlier runs.")
    manifests = {
        arm: read_manifest(merged / arm / "manifest.json") for arm in ("control", "merged")
    }
    holdouts = [[r for r in m["records"] if r["split"] != "train"] for m in manifests.values()]
    if holdouts[0] != holdouts[1]:
        raise ValueError("Both arms must use identical validation and test records.")
    protocol = {
        "recorded_on": "2026-11-08",
        "seed": 42,
        "design": "Paired fixed-budget continuation from the deployed Torch checkpoints, not from scratch.",
        "initialization": {
            "detector": {
                "path": str(DETECTOR),
                "sha256": hashlib.sha256(DETECTOR.read_bytes()).hexdigest(),
            },
            "classifier": {
                "path": str(CLASSIFIER),
                "sha256": hashlib.sha256(CLASSIFIER.read_bytes()).hexdigest(),
            },
        },
        "manifests": {arm: m["fingerprint"] for arm, m in manifests.items()},
        "budgets": {
            "detector_epochs": 6,
            "detector_samples_per_epoch": 1424,
            "classifier_epochs": 6,
            "classifier_samples_per_epoch": 12000,
        },
        "selection": "Detector checkpoint: equal-source mean validation mAP50. Classifier: equal-source mean validation macro-F1. Final detection threshold: equal-source mean typed F1 on validation only; overlap fixed at 0.4.",
        "threshold_candidates": [0.15, 0.2, 0.25, 0.3],
        "overlap": 0.4,
        "primary_metric": "Equal-source mean typed F1 = mean_source(2*correct_type_color/(annotations+predictions)).",
        "secondary_metrics": [
            "typed_piece_recall",
            "typed_prediction_precision",
            "localization_recall",
            "conditional_type_color_accuracy",
            "missed_pieces",
            "unmatched_predictions",
            "per_class_recall_and_confusion",
            "king_recall",
            "paired_group_bootstrap",
        ],
        "promotion_gate": {
            "minimum_macro_typed_f1_gain": 0.01,
            "maximum_source_recall_or_precision_drop": 0.02,
            "maximum_king_recall_drop": 0.02,
            "requires": "Beat both paired control and deployed baseline; pass gates on each source. Positive group-bootstrap lower bound against control. ONNX/runtime verification required separately.",
        },
        "limitations": [
            "One seed; cannot isolate all stochastic variation.",
            "Top Down test has only 17 images, with no verified physical-set IDs.",
            "No square/whole-board labels; no claim of improved whole-board accuracy.",
            "Both source test collections have prior development exposure; regression evidence only.",
            "75/25 source mixture is predeclared, not optimized using test results.",
        ],
    }
    save_json(output / "protocol.json", protocol)
    for arm in manifests:
        weights = {"chess-v2": 1.0} if arm == "control" else {"chess-v2": 0.75, "top-down": 0.25}
        detector = {
            **json.loads(Path("scanner/ml/configs/chess-v2-baseline.json").read_text()),
            "epochs": 6,
            "warmup_epochs": 0,
            "patience": 6,
            "learning_rate": 0.0003,
            "backbone_learning_rate": 0.00003,
            "samples_per_epoch": 1424,
            "source_weights": weights,
            "source_balanced_validation": True,
            "initialize_from": str(DETECTOR),
            "initialization_manifest": str(BASE),
        }
        classifier = {
            **json.loads(Path("scanner/ml/configs/king-focused.json").read_text()),
            "epochs": 6,
            "patience": 6,
            "source_weights": weights,
            "source_balanced_validation": True,
            "initialize_from": str(CLASSIFIER),
            "initialization_manifest": str(BASE),
        }
        save_json(output / arm / "detector-config.json", detector)
        save_json(output / arm / "classifier-config.json", classifier)
    return protocol


def fit(merged, output):
    protocol = json.loads((output / "protocol.json").read_text())
    for info in protocol["initialization"].values():
        if hashlib.sha256(Path(info["path"]).read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError("Initialization checkpoint changed after protocol registration.")
    for arm in ("control", "merged"):
        manifest = merged / arm / "manifest.json"
        if read_manifest(manifest)["fingerprint"] != protocol["manifests"][arm]:
            raise ValueError("Manifest changed after protocol registration.")
        for stage in ("detector", "classifier"):
            folder = output / arm / stage
            completed = output / arm / f"{stage}-completed.json"
            if completed.exists():
                if (
                    hashlib.sha256((folder / "best.pt").read_bytes()).hexdigest()
                    != json.loads(completed.read_text())["sha256"]
                ):
                    raise ValueError("Completed stage checkpoint changed.")
                continue
            command = (
                [sys.executable, "-m", "scanner.ml", "train"]
                if stage == "detector"
                else [sys.executable, "-m", "scanner.ml.classifier"]
            )
            command += [
                "--manifest",
                str(manifest),
                "--config",
                str(output / arm / f"{stage}-config.json"),
                "--output",
                str(folder),
            ]
            if stage == "classifier":
                command += ["--cache", str(output / arm / "crops")]
            print(f"Training {arm}/{stage}; log: {output / arm / (stage + '.log')}", flush=True)
            with (output / arm / f"{stage}.log").open("x") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            save_json(
                completed, {"sha256": hashlib.sha256((folder / "best.pt").read_bytes()).hexdigest()}
            )
            print(f"Completed {arm}/{stage}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "fit"))
    parser.add_argument("--merge", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_experiment(args.merge, args.output)
    else:
        fit(args.merge, args.output)
