"""Locked, source-stratified comparison of the paired merge experiment."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from .benchmark import piece_diagnostics
from .classifier import load_classifier
from .data import CocoPieces, read_manifest, save_json
from .experiment import classify_predictions
from .merge_experiment import CLASSIFIER, DETECTOR
from .metrics import collect_predictions
from .model import choose_device, load_checkpoint
from .piece_errors import analyze
from .postprocess import resolve_duplicates


def typed_f1(metrics):
    denominator = metrics["annotated_pieces"] + metrics["predictions"]
    return 2 * metrics["correct_type_color"] / denominator if denominator else 0.0


def summarize(predictions, records, threshold):
    combined = piece_diagnostics(predictions, records, threshold)
    combined["typed_f1"] = typed_f1(combined)
    sources = {}
    for source in sorted({r["source_dataset"] for r in records}):
        subset = [r for r in records if r["source_dataset"] == source]
        ids = {r["id"] for r in subset}
        outputs = [p for p in predictions if p["image_id"] in ids]
        metrics = piece_diagnostics(outputs, subset, threshold)
        errors, _ = analyze(outputs, subset, threshold)
        metrics.update(
            typed_f1=typed_f1(metrics),
            per_class=errors["by_actual_class"],
            per_type=errors["by_actual_type"],
            predicted_classes=errors["by_predicted_class"],
            evaluation_groups=len({r["evaluation_group"] for r in subset}),
        )
        sources[source] = metrics
    return {
        "combined": combined,
        "per_source": sources,
        "macro_source_typed_f1": sum(m["typed_f1"] for m in sources.values()) / len(sources),
    }


def image_counts(predictions, records, threshold):
    by_id = {p["image_id"]: p for p in predictions}
    result = []
    for record in records:
        metrics = piece_diagnostics([by_id[record["id"]]], [record], threshold)
        result.append(
            {
                "image_id": record["id"],
                "source": record["source_dataset"],
                "group": record["evaluation_group"],
                **{
                    key: metrics[key]
                    for key in ("annotated_pieces", "predictions", "correct_type_color")
                },
            }
        )
    return result


def paired_bootstrap(candidate, control, repetitions=2000, seed=42):
    if [(r["image_id"], r["source"], r["group"], r["annotated_pieces"]) for r in candidate] != [
        (r["image_id"], r["source"], r["group"], r["annotated_pieces"]) for r in control
    ]:
        raise ValueError("Paired bootstrap requires identical ordered image/group ground truth.")
    groups = defaultdict(lambda: defaultdict(lambda: np.zeros((2, 3))))
    for pair in zip(candidate, control, strict=True):
        for arm, row in enumerate(pair):
            groups[row["source"]][row["group"]][arm] += [
                row["correct_type_color"],
                row["annotated_pieces"],
                row["predictions"],
            ]
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(repetitions):
        delta = []
        for source_groups in groups.values():
            values = np.stack(list(source_groups.values()))
            totals = values[rng.integers(0, len(values), len(values))].sum(axis=0)
            scores = 2 * totals[:, 0] / np.maximum(totals[:, 1] + totals[:, 2], 1)
            delta.append(float(scores[0] - scores[1]))
        samples.append(float(np.mean(delta)))
    return {
        "repetitions": repetitions,
        "seed": seed,
        "groups_per_source": {s: len(g) for s, g in groups.items()},
        "macro_typed_f1_delta_95_percentile_interval": np.quantile(
            samples, [0.025, 0.975]
        ).tolist(),
        "limitation": "Few groups, one training seed, and unknown physical-set identity limit inference. Not a generalization guarantee.",
    }


def decision(results, bootstrap, gate):
    candidate = results["merged"]["test"]
    failures = []
    for name in ("control", "deployed"):
        reference = results[name]["test"]
        if (
            candidate["macro_source_typed_f1"] - reference["macro_source_typed_f1"]
            < gate["minimum_macro_typed_f1_gain"]
        ):
            failures.append(f"Macro typed F1 gain below gate versus {name}.")
        for source, metrics in candidate["per_source"].items():
            baseline = reference["per_source"][source]
            for metric in ("typed_piece_recall", "typed_prediction_precision"):
                if (metrics[metric] or 0) < (baseline[metric] or 0) - gate[
                    "maximum_source_recall_or_precision_drop"
                ]:
                    failures.append(f"{source} {metric} regressed versus {name}.")
            for metric_set, ref_set in ((metrics["per_type"], baseline["per_type"]),):
                king = next(row for row in metric_set if row["piece"] == "king")
                old_king = next(row for row in ref_set if row["piece"] == "king")
                recall = king["correct"] / king["support"] if king["support"] else 0
                old_recall = old_king["correct"] / old_king["support"] if old_king["support"] else 0
                if recall < old_recall - gate["maximum_king_recall_drop"]:
                    failures.append(f"{source} King typed recall regressed versus {name}.")
    if bootstrap["macro_typed_f1_delta_95_percentile_interval"][0] <= 0:
        failures.append(
            "Paired group-bootstrap interval does not establish a positive gain versus control."
        )
    return {
        "accuracy_gate_passed": not failures,
        "failures": failures,
        "deployed_models_changed": False,
        "next_step": "Run ONNX parity/runtime checks before any promotion."
        if not failures
        else "Keep deployed models; retain this candidate as an experiment.",
    }


def evaluate(merged, training, output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new evaluation directory; never overwrite recorded results.")
    protocol = json.loads((training / "protocol.json").read_text())
    deployed_selection = json.loads(Path("scanner/models/onnx/manifest.json").read_text())[
        "selection"
    ]
    if any(
        deployed_selection[f"{stage}_sha256"] != protocol["initialization"][stage]["sha256"]
        for stage in ("detector", "classifier")
    ):
        raise ValueError("Deployed ONNX models no longer match the registered baseline.")
    manifest = read_manifest(merged / "merged/manifest.json")
    if manifest["fingerprint"] != protocol["manifests"]["merged"]:
        raise ValueError("Evaluation manifest differs from the registered protocol.")
    device = choose_device("auto")
    torch.set_num_threads(4)
    paths = {
        "deployed": (DETECTOR, CLASSIFIER),
        **{
            arm: (training / arm / "detector/best.pt", training / arm / "classifier/best.pt")
            for arm in ("control", "merged")
        },
    }
    sources, selections, results, counts = {}, {}, {}, {}
    for arm, pair in paths.items():
        sources[arm] = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in zip(("detector", "classifier"), pair, strict=True)
        }
        for stage, digest in sources[arm].items():
            expected = (
                protocol["initialization"][stage]["sha256"]
                if arm == "deployed"
                else json.loads((training / arm / f"{stage}-completed.json").read_text())["sha256"]
            )
            if digest != expected:
                raise ValueError("Checkpoint changed after training/protocol registration.")
    # Finish and persist every validation choice before collecting any test predictions.
    for split in ("valid", "test"):
        dataset = CocoPieces(manifest, split, input_size=320)
        for arm, (detector_path, classifier_path) in paths.items():
            print(f"Evaluating {arm}/{split}", flush=True)
            detector, checkpoint = load_checkpoint(detector_path, device)
            expected = (
                protocol["manifests"][arm]
                if arm != "deployed"
                else json.loads(
                    Path(
                        "scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json"
                    ).read_text()
                )["fingerprint"]
            )
            if checkpoint["dataset_fingerprint"] != expected:
                raise ValueError("Detector training manifest mismatch.")
            raw, timing = collect_predictions(detector, dataset, device, batch_size=8)
            del detector
            classifier, checkpoint = load_classifier(classifier_path, device)
            if checkpoint["dataset_fingerprint"] != expected:
                raise ValueError("Classifier training manifest mismatch.")
            classified = classify_predictions(
                classifier,
                checkpoint,
                manifest,
                dataset.records,
                raw,
                device,
                threshold=min(protocol["threshold_candidates"]),
            )
            del classifier
            save_json(output / arm / f"{split}-classified.json", classified)
            if split == "valid":
                thresholds = [0.2] if arm == "deployed" else protocol["threshold_candidates"]
                sweep = []
                for threshold in thresholds:
                    filtered = [
                        resolve_duplicates(p, threshold=threshold, overlap=protocol["overlap"])
                        for p in classified
                    ]
                    metrics = summarize(filtered, dataset.records, threshold)
                    sweep.append({"threshold": threshold, "metrics": metrics})
                best = max(
                    sweep,
                    key=lambda row: (row["metrics"]["macro_source_typed_f1"], row["threshold"]),
                )
                selections[arm] = {
                    "threshold": best["threshold"],
                    "overlap": protocol["overlap"],
                    "pipeline": "combined",
                    "dataset_fingerprint": expected,
                    "detector_sha256": sources[arm]["detector"],
                    "classifier_sha256": sources[arm]["classifier"],
                }
                save_json(output / arm / "validation-sweep.json", sweep)
                save_json(output / arm / "selection.json", selections[arm])
            settings = selections[arm]
            filtered = [
                resolve_duplicates(p, threshold=settings["threshold"], overlap=settings["overlap"])
                for p in classified
            ]
            metrics = summarize(filtered, dataset.records, settings["threshold"])
            metrics["detector_timing"] = timing
            results.setdefault(arm, {})[split] = metrics
            save_json(output / arm / f"{split}-predictions.json", filtered)
            save_json(output / arm / f"{split}-metrics.json", metrics)
            if split == "test":
                counts[arm] = image_counts(filtered, dataset.records, settings["threshold"])
                save_json(output / arm / "test-image-counts.json", counts[arm])
            print(
                json.dumps(
                    {
                        "arm": arm,
                        "split": split,
                        "threshold": settings["threshold"],
                        "macro_typed_f1": metrics["macro_source_typed_f1"],
                        "source_recall": {
                            s: m["typed_piece_recall"] for s, m in metrics["per_source"].items()
                        },
                    }
                ),
                flush=True,
            )
    bootstrap = paired_bootstrap(counts["merged"], counts["control"])
    report = {
        "protocol": protocol,
        "models": sources,
        "selections": selections,
        "results": results,
        "bootstrap": bootstrap,
        "decision": decision(results, bootstrap, protocol["promotion_gate"]),
    }
    save_json(output / "results.json", report)
    print(json.dumps(report["decision"], indent=2), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merge", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.merge, args.training, args.output)
