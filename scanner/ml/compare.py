"""Read-only overlap checks between separately prepared source datasets."""

from pathlib import Path

from PIL import Image

from .data import read_manifest, resolve_image, save_json
from .grouping import near_pairs, thumbnail_features


def compare_manifests(first_path, second_path, output):
    manifests = [read_manifest(path) for path in (first_path, second_path)]
    rows = []
    for source, manifest in enumerate(manifests):
        root = Path(manifest["dataset_root"])
        for record in manifest["records"]:
            with Image.open(resolve_image(root, record["file"])) as image:
                thumb, hashes = thumbnail_features(image)
            rows.append(
                {
                    "source": source,
                    "key": record["file"],
                    "sha256": record["sha256"],
                    "thumb": thumb,
                    "phashes": hashes,
                }
            )
    exact = [
        (left["key"], right["key"])
        for left in rows
        if left["source"] == 0
        for right in rows
        if right["source"] == 1 and left["sha256"] == right["sha256"]
    ]
    candidates = []
    for pair in near_pairs(rows):
        left, right = rows[pair["first"]], rows[pair["second"]]
        if left["source"] != right["source"]:
            candidates.append({**pair, "first": left["key"], "second": right["key"]})
    result = {
        "format_version": 1,
        "first_fingerprint": manifests[0]["fingerprint"],
        "second_fingerprint": manifests[1]["fingerprint"],
        "first_images": len(manifests[0]["records"]),
        "second_images": len(manifests[1]["records"]),
        "exact_byte_pairs": exact,
        "perceptual_candidates": candidates,
        "limitations": [
            "No files or splits are changed by this comparison.",
            "Candidates are not confirmed duplicates; absence of matches does not establish source independence.",
            "Arbitrary crops, perspective changes, and non-quarter-turn rotations may evade this check.",
            "Do not combine sources before reviewing overlap and capture provenance.",
        ],
    }
    save_json(output, result)
    return {
        "exact_byte_pairs": len(exact),
        "perceptual_candidates": len(candidates),
        "report": str(output),
    }
