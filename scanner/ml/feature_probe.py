"""Bounded, validation-only frozen-DINO comparison; never exports a production model."""

import argparse
import hashlib
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from .classifier import classification_metrics, crop_transform, load_classifier
from .data import save_json
from .model import choose_device

DINO_REVISION = "7c446df5b9f45747937fb0d72314eb9f7b66930a"


def select_records(index, split, per_class):
    if split not in {"train", "valid"} or not 1 <= per_class <= 10000:
        raise ValueError("Use train/valid and a positive bounded sample count.")
    classes = defaultdict(list)
    for row in index["records"]:
        if row["split"] == split:
            classes[row["label"]].append(row)
    selected = []
    randomizer = random.Random(42)
    for label in sorted(classes):
        records = sorted(classes[label], key=lambda r: r["crop"])
        randomizer.shuffle(records)
        selected.extend(records[:per_class])
    return selected


def metrics(logits, records):
    confusion = np.zeros((12, 12), dtype=np.int64)
    np.add.at(confusion, ([r["label"] - 1 for r in records], logits.argmax(axis=1)), 1)
    return classification_metrics(confusion)


def run(cache, checkpoint_path, output, train_per_class=128, valid_per_class=64):
    if output.exists():
        raise ValueError("Use a fresh output path.")
    index = json.loads((cache / "index.json").read_text())
    training = select_records(index, "train", train_per_class)
    validation = select_records(index, "valid", valid_per_class)
    if {r["label"] for r in training} != set(range(1, 13)) or not validation:
        raise ValueError("Training requires all twelve classes and nonempty validation.")

    def groups(rows):
        return {r.get("split_group") or r["source_sha256"] for r in rows}

    if groups(training) & groups(validation):
        raise ValueError("Training and validation source groups overlap.")
    torch.set_num_threads(4)
    device = choose_device()
    baseline, checkpoint = load_classifier(checkpoint_path, device)
    if checkpoint["dataset_fingerprint"] != index["dataset_fingerprint"]:
        raise ValueError("Baseline and crop data differ.")
    transform = crop_transform(False)

    def extract(model, rows):
        features = []
        started = time.perf_counter()
        with torch.inference_mode():
            for start in range(0, len(rows), 16):
                tensors = []
                for row in rows[start : start + 16]:
                    with Image.open(cache / row["crop"]) as image:
                        tensors.append(transform(image.convert("RGB")))
                features.extend(model(torch.stack(tensors).to(device)).cpu().numpy())
        return np.asarray(features), (time.perf_counter() - started) * 1000

    baseline_logits, baseline_ms = extract(baseline, validation)
    del baseline
    print("Baseline evaluated. Loading pinned official DINO ViT-S/8 backbone...", flush=True)
    encoder = (
        torch.hub.load(
            f"facebookresearch/dino:{DINO_REVISION}", "dino_vits8", pretrained=True, trust_repo=True
        )
        .to(device)
        .eval()
    )
    for parameter in encoder.parameters():
        parameter.requires_grad_(False)
    parameter_bytes = sum(p.numel() * p.element_size() for p in encoder.parameters())
    train_x, train_ms = extract(encoder, training)
    valid_x, valid_ms = extract(encoder, validation)
    # A fixed-feature ridge head is a reproducible small-data baseline, not DINO fine-tuning.
    mean, scale = train_x.mean(axis=0), np.maximum(train_x.std(axis=0), 1e-6)
    train_x = np.column_stack(((train_x - mean) / scale, np.ones(len(train_x))))
    valid_x = np.column_stack(((valid_x - mean) / scale, np.ones(len(valid_x))))
    labels = np.eye(12)[[r["label"] - 1 for r in training]]
    candidates = []
    for regularization in (0.01, 0.1, 1.0, 10.0):
        penalty = np.eye(train_x.shape[1]) * regularization
        penalty[-1, -1] = 0
        weights = np.linalg.solve(train_x.T @ train_x + penalty, train_x.T @ labels)
        candidates.append(
            {"regularization": regularization, "metrics": metrics(valid_x @ weights, validation)}
        )
    save_json(
        output,
        {
            "method": "frozen_dino_vits8_ridge_pilot_v1",
            "encoder_revision": DINO_REVISION,
            "dataset_fingerprint": index["dataset_fingerprint"],
            "crop_fingerprint": index["fingerprint"],
            "baseline_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
            "device": str(device),
            "train_samples": len(training),
            "validation_samples": len(validation),
            "baseline": metrics(baseline_logits, validation),
            "candidates": candidates,
            "timings_ms": {
                "baseline_validation": baseline_ms,
                "dino_train_features": train_ms,
                "dino_validation": valid_ms,
            },
            "dino_backbone_parameter_mib": parameter_bytes / 1024**2,
            "selection_split": "valid",
            "test_used": False,
            "promoted": False,
            "training_crops": [r["crop"] for r in training],
            "validation_crops": [r["crop"] for r in validation],
            "limitations": [
                "Class-capped ground-truth crops, not detector proposals or full boards.",
                "Current baseline used more training data; this is a bounded feasibility probe, not an architecture ranking.",
                "Validation selects the head; no independent test or unfamiliar-set claim.",
                "Batch feature extraction includes image IO; not browser/server request latency.",
            ],
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-per-class", type=int, default=128)
    parser.add_argument("--valid-per-class", type=int, default=64)
    args = parser.parse_args()
    run(args.cache, args.checkpoint, args.output, args.train_per_class, args.valid_per_class)
