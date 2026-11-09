"""Versioned two-source manifests with frozen holdouts and conservative overlap checks."""

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from .data import CLASSES, read_manifest, resolve_image, save_json
from .grouping import Groups, near_pairs, thumbnail_features


def partition(rows, pairs):
    groups = Groups(len(rows))
    seen = {}
    for index, row in enumerate(rows):
        keys = [
            ("pixels", row["pixel_sha256"]),
            ("source", row["source_dataset"], row["source_group"]),
        ]
        if row.get("split_group"):
            keys.append(("capture", row["source_dataset"], row["split_group"]))
        for key in keys:
            if key in seen:
                groups.join(index, seen[key])
            seen[key] = index
    for pair in pairs:
        groups.join(pair["first"], pair["second"])
    components = defaultdict(list)
    for index in range(len(rows)):
        components[groups.find(index)].append(index)
    excluded, retained = [], []
    priority = {"train": 0, "valid": 1, "test": 2}
    for indices in components.values():
        base_splits = {rows[i]["split"] for i in indices if rows[i]["source_index"] == 0}
        if len(base_splits) > 1:
            raise ValueError("Overlap crosses frozen base splits; review before training.")
        split = max((rows[i]["split"] for i in indices), key=priority.get)
        group = hashlib.sha256(
            "\n".join(sorted(rows[i]["key"] for i in indices)).encode()
        ).hexdigest()[:16]
        pixels = {}
        for i in sorted(indices, key=lambda i: (rows[i]["source_index"], rows[i]["key"])):
            row = rows[i]
            reason = None
            if row["source_index"] == 0 and row["split"] != split:
                # Never relocate a base record or expose an added holdout to base training.
                raise ValueError(
                    "Added holdout overlaps base training/validation; manual review required."
                )
            if row["split"] != split:
                reason = "related image occurs in a more protected split"
            elif row["pixel_sha256"] in pixels:
                previous = pixels[row["pixel_sha256"]]
                if row["boxes"] != previous["boxes"] or row["labels"] != previous["labels"]:
                    raise ValueError(
                        "Identical images have conflicting annotations; review required."
                    )
                if row["source_index"] == 0:
                    raise ValueError(
                        "Base contains exact pixel duplicates; curate separately first."
                    )
                reason = "exact decoded-pixel duplicate"
            if reason:
                excluded.append({"key": row["key"], "split": row["split"], "reason": reason})
            else:
                pixels[row["pixel_sha256"]] = row
                retained.append({**row, "evaluation_group": group})
    return sorted(retained, key=lambda row: row["id"]), excluded


def manifest_for(rows, root, sources, arm):
    records = []
    for row in rows:
        if arm == "control" and row["source_index"] == 1 and row["split"] == "train":
            continue
        records.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"thumb", "phashes", "key", "source_index"}
            }
        )
    fingerprint = hashlib.sha256(
        json.dumps({"classes": CLASSES, "records": records}, sort_keys=True).encode()
    ).hexdigest()
    return {
        "format_version": 1,
        "task": "piece_detection",
        "dataset": f"two-source-{arm}",
        "dataset_root": str(root),
        "classes": list(CLASSES),
        "records": records,
        "fingerprint": fingerprint,
        "sources": sources,
        "splits_preserved": True,
    }


def merge(base_path, added_path, output):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new merge directory; existing datasets are immutable.")
    manifests = [read_manifest(path) for path in (base_path, added_path)]
    if manifests[0]["dataset"] == manifests[1]["dataset"]:
        raise ValueError("Two distinct named sources are required.")
    root = Path(os.path.commonpath([m["dataset_root"] for m in manifests])).resolve()
    rows, sources = [], []
    for source, manifest in enumerate(manifests):
        sources.append(
            {
                key: manifest[key]
                for key in ("dataset", "fingerprint", "source", "attribution", "license")
            }
        )
        for record in manifest["records"]:
            path = resolve_image(Path(manifest["dataset_root"]), record["file"])
            with Image.open(path) as original:
                image = original.convert("RGB")
                thumb, hashes = thumbnail_features(image)
                digest = hashlib.sha256(f"{image.size}:".encode() + image.tobytes()).hexdigest()
            rows.append(
                {
                    **record,
                    "id": len(rows) + 1,
                    "source_dataset": manifest["dataset"],
                    "source_index": source,
                    "original_id": record["id"],
                    "original_file": record["file"],
                    "key": f"{source}:{record['file']}",
                    "file": str(path.relative_to(root)),
                    "pixel_sha256": digest,
                    "thumb": thumb,
                    "phashes": hashes,
                }
            )
            if len(rows) % 200 == 0:
                print(f"Audited {len(rows)} images", flush=True)
    pairs = near_pairs(rows)
    retained, excluded = partition(rows, pairs)
    report = {
        "valid": True,
        "sources": sources,
        "excluded": excluded,
        "perceptual_pairs": [
            {**p, "first": rows[p["first"]]["key"], "second": rows[p["second"]]["key"]}
            for p in pairs
        ],
        "limitations": [
            "No physical-set IDs exist for Top Down; grouped image holdouts do not prove unseen-set generalization.",
            "Perceptual checks can miss arbitrary crops or perspective changes.",
            "Unknown filename prefixes are not asserted to be capture sessions.",
            "Existing test sets are regression benchmarks, not new external tests.",
        ],
    }
    for arm in ("control", "merged"):
        manifest = manifest_for(retained, root, sources, arm)
        counts = Counter((r["source_dataset"], r["split"]) for r in manifest["records"])
        if any(not counts[(m["dataset"], split)] for m in manifests for split in ("valid", "test")):
            raise ValueError("Overlap filtering emptied a source holdout.")
        report[arm] = {
            "fingerprint": manifest["fingerprint"],
            "counts": {f"{source}/{split}": n for (source, split), n in sorted(counts.items())},
        }
        save_json(output / arm / "manifest.json", manifest)
    save_json(output / "audit.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--added", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = merge(args.base, args.added, args.output)
    print(json.dumps({key: result[key] for key in ("control", "merged", "excluded")}, indent=2))
