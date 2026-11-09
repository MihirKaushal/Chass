"""Explicit, audited checkpoint transfer and fixed-budget source sampling."""

import math
from collections import Counter
from pathlib import Path

from .data import read_manifest


def validate_transfer(checkpoint, target, source_path):
    source = read_manifest(Path(source_path))
    if source["fingerprint"] != checkpoint["dataset_fingerprint"]:
        raise ValueError("Initialization checkpoint and source manifest differ.")
    target_by_hash = {r["sha256"]: r for r in target["records"]}
    for record in source["records"]:
        target_record = target_by_hash.get(record["sha256"])
        if target_record is None or any(
            target_record[key] != record[key] for key in ("split", "boxes", "labels")
        ):
            raise ValueError("Transfer must preserve all source labels and split assignments.")


def sampling_weights(records, source_weights, class_multipliers=None):
    sources = {r["source_dataset"] for r in records}
    if set(source_weights) != sources or any(
        not math.isfinite(w) or w <= 0 for w in source_weights.values()
    ):
        raise ValueError("Provide positive weights for exactly the training sources.")
    if class_multipliers is None:
        counts = Counter(r["source_dataset"] for r in records)
        return [source_weights[r["source_dataset"]] / counts[r["source_dataset"]] for r in records]
    counts = Counter((r["source_dataset"], r["label"]) for r in records)
    normalizers = {
        source: sum(class_multipliers.get(label, 1) for s, label in counts if s == source)
        for source in sources
    }
    return [
        source_weights[r["source_dataset"]]
        * class_multipliers.get(r["label"], 1)
        / (normalizers[r["source_dataset"]] * counts[r["source_dataset"], r["label"]])
        for r in records
    ]
