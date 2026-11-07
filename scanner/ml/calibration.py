"""Offline temperature-scaling diagnostics. Never changes production model scores."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .data import save_json


def probabilities(logits, temperature=1.0):
    values = np.asarray(logits, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != 12
        or not len(values)
        or not np.isfinite(values).all()
    ):
        raise ValueError("Supply finite logits for all twelve piece classes.")
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("Temperature must be positive and finite.")
    scaled = (values - values.max(axis=1, keepdims=True)) / temperature
    values = np.exp(scaled)
    return values / values.sum(axis=1, keepdims=True)


def diagnostics(logits, labels, temperature=1.0, bins=10):
    probs = probabilities(logits, temperature)
    labels = np.asarray(labels)
    if (
        labels.shape != (len(probs),)
        or labels.dtype.kind not in "iu"
        or np.any((labels < 0) | (labels >= 12))
    ):
        raise ValueError("Supply a zero-based class label for each logit row.")
    if type(bins) is not int or not 1 <= bins <= 100:
        raise ValueError("Use 1 to 100 calibration bins.")
    correct = probs.argmax(axis=1) == labels
    scores = probs.max(axis=1)
    reliability, ece = [], 0.0
    bucket = np.minimum((scores * bins).astype(int), bins - 1)
    for index in range(bins):
        mask = bucket == index
        count = int(mask.sum())
        accuracy = float(correct[mask].mean()) if count else None
        confidence = float(scores[mask].mean()) if count else None
        if count:
            ece += count / len(probs) * abs(accuracy - confidence)
        reliability.append(
            {
                "low": index / bins,
                "high": (index + 1) / bins,
                "count": count,
                "accuracy": accuracy,
                "confidence": confidence,
            }
        )
    return {
        "samples": len(probs),
        "accuracy": float(correct.mean()),
        "nll": float(-np.log(np.clip(probs[np.arange(len(probs)), labels], 1e-15, 1)).mean()),
        "brier_multiclass": float(((probs - np.eye(12)[labels]) ** 2).sum(axis=1).mean()),
        "ece": float(ece),
        "reliability_bins": reliability,
    }


def fit_temperature(logits, labels):
    # A bounded one-parameter search includes the unchanged baseline exactly.
    candidates = sorted({1.0, *np.geomspace(0.05, 10, 241).tolist()})
    return min(candidates, key=lambda t: diagnostics(logits, labels, t)["nll"])


def evaluate_validation(payload):
    if payload.get("split") != "valid":
        raise ValueError("Fit calibration on validation only, never train or test.")
    rows = payload["records"]
    if not rows or any(not row.get("group_id") for row in rows):
        raise ValueError("Every crop needs its original image/session group.")
    groups = sorted(
        {row["group_id"] for row in rows},
        key=lambda group: hashlib.sha256(f"chass-calibration-v1:{group}".encode()).hexdigest(),
    )
    if len(groups) < 4:
        raise ValueError("At least four independent validation groups are required.")
    fit_groups = set(groups[: len(groups) // 2])
    fit = [r for r in rows if r["group_id"] in fit_groups]
    check = [r for r in rows if r["group_id"] not in fit_groups]
    temperature = fit_temperature([r["logits"] for r in fit], [r["label"] for r in fit])
    logits, labels = [r["logits"] for r in check], [r["label"] for r in check]
    return {
        "method": "temperature_scaling_grouped_validation_v1",
        "temperature": temperature,
        "fit_groups": sorted(fit_groups),
        "evaluation_groups": sorted(set(groups) - fit_groups),
        "fit_samples": len(fit),
        "baseline": diagnostics(logits, labels),
        "candidate": diagnostics(logits, labels, temperature),
        "model_sha256": payload.get("model_sha256"),
        "dataset_fingerprint": payload.get("dataset_fingerprint"),
        "promoted": False,
        "limitations": [
            "Conditional on provided piece crops; does not measure missing pieces or whole boards.",
            "Existing validation data, not independent physical-set generalization.",
            "Calibration changes score interpretation, not the predicted class.",
        ],
    }


def export_logits(checkpoint_path, cache):
    import torch
    from torch.utils.data import DataLoader

    from .classifier import PieceCrops, load_classifier
    from .model import choose_device

    index = json.loads((cache / "index.json").read_text())
    device = choose_device()
    torch.set_num_threads(4)
    model, checkpoint = load_classifier(checkpoint_path, device)
    if checkpoint["dataset_fingerprint"] != index["dataset_fingerprint"]:
        raise ValueError("Classifier and crop datasets differ.")
    dataset = PieceCrops(cache, index, "valid")
    rows, offset = [], 0
    with torch.inference_mode():
        for images, labels in DataLoader(dataset, batch_size=64, shuffle=False):
            logits = model(images.to(device)).cpu().tolist()
            for values, label in zip(logits, labels.tolist(), strict=True):
                record = dataset.records[offset]
                rows.append(
                    {
                        "group_id": str(record.get("split_group") or record["source_sha256"]),
                        "crop": record["crop"],
                        "label": label,
                        "logits": values,
                    }
                )
                offset += 1
    return {
        "split": "valid",
        "records": rows,
        "dataset_fingerprint": index["dataset_fingerprint"],
        "model_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--logits", type=Path)
    source.add_argument("--checkpoint", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path.")
    if args.checkpoint and not args.cache:
        parser.error("A checkpoint requires --cache.")
    if args.checkpoint:
        index = json.loads((args.cache / "index.json").read_text())
        validation = [r for r in index["records"] if r["split"] == "valid"]
        groups = {r.get("split_group") or r["source_sha256"] for r in validation}
        if len(groups) < 4:
            result = {
                "status": "blocked",
                "reason": "Need at least four independent validation groups.",
                "validation_groups": len(groups),
                "validation_crops": len(validation),
                "temperature": None,
                "promoted": False,
                "dataset_fingerprint": index["dataset_fingerprint"],
                "model_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
            }
            save_json(args.output, result)
            print(json.dumps(result))
            return
    payload = (
        json.loads(args.logits.read_text())
        if args.logits
        else export_logits(args.checkpoint, args.cache)
    )
    if payload.get("split") != "valid":
        parser.error("Calibration accepts validation data only, never train or test.")
    groups = {r["group_id"] for r in payload["records"]}
    if len(groups) < 4:
        # Do not break capture groups apart merely to make calibration appear measurable.
        result = {
            "status": "blocked",
            "reason": "Need at least four independent validation groups.",
            "validation_groups": len(groups),
            "temperature": None,
            "candidate": None,
            "baseline": diagnostics(
                [r["logits"] for r in payload["records"]], [r["label"] for r in payload["records"]]
            ),
            "model_sha256": payload.get("model_sha256"),
            "dataset_fingerprint": payload.get("dataset_fingerprint"),
            "promoted": False,
        }
    else:
        result = evaluate_validation(payload)
    result["input_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    save_json(args.output, result)
    print(
        json.dumps(
            {key: result[key] for key in ("temperature", "baseline", "candidate", "promoted")}
        )
    )


if __name__ == "__main__":
    main()
