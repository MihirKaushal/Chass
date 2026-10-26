"""Versioned COCO curation. Raw inputs and the original benchmark are never rewritten."""

import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

from PIL import Image

from .data import CLASSES, SPLITS, prepare_dataset, resolve_image, save_json, source_group
from .grouping import assign_splits, capture_group, near_pairs, thumbnail_features
from .metrics import box_iou


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def reviewed_rotation(image, rotation):
    turns = {
        "none": None,
        "cw": Image.Transpose.ROTATE_270,
        "half": Image.Transpose.ROTATE_180,
        "ccw": Image.Transpose.ROTATE_90,
    }
    if rotation not in turns:
        raise ValueError("Unknown reviewed rotation")
    return image if turns[rotation] is None else image.transpose(turns[rotation])


def xyxy(box):
    x, y, width, height = box
    return [x, y, x + width, y + height]


def clean_annotations(
    annotations,
    categories,
    size,
    *,
    drops=None,
    duplicate_iou=0.9,
    overlap_review_iou=None,
    verified_empty=False,
):
    drops = drops or {}
    retained, changes, issues = [], [], []
    for annotation in sorted(annotations, key=lambda item: item["id"]):
        old_id = annotation["id"]
        if str(old_id) in drops:
            changes.append(
                {
                    "action": "reviewed_annotation_removed",
                    "annotation_id": old_id,
                    "reason": drops[str(old_id)],
                }
            )
            continue
        label = categories.get(annotation["category_id"])
        box = annotation.get("bbox", [])
        if (
            label not in CLASSES[1:]
            or len(box) != 4
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in box)
        ):
            issues.append(f"Invalid label/coordinates: annotation {old_id}")
            continue
        x, y, width, height = box
        if min(width, height) < 0:
            issues.append(f"Negative box extent: annotation {old_id}")
            continue
        if min(width, height) == 0:
            changes.append(
                {"action": "zero_area_annotation_removed", "annotation_id": old_id, "bbox": box}
            )
            continue
        if (
            min(x, y) < 0
            or x + width > size[0] + 1e-4
            or y + height > size[1] + 1e-4
            or annotation.get("iscrowd", 0)
        ):
            issues.append(f"Unrecoverable box geometry/crowd region: annotation {old_id}")
            continue
        candidate = {"id": old_id, "label": label, "bbox": box}
        duplicate = next(
            (
                other
                for other in retained
                if other["label"] == label
                and box_iou(xyxy(box), xyxy(other["bbox"])) >= duplicate_iou
            ),
            None,
        )
        if duplicate:
            changes.append(
                {
                    "action": "duplicate_annotation_removed",
                    "annotation_id": old_id,
                    "kept_annotation_id": duplicate["id"],
                    "iou": box_iou(xyxy(box), xyxy(duplicate["bbox"])),
                }
            )
        else:
            retained.append(candidate)
    unknown = set(drops) - {str(annotation["id"]) for annotation in annotations}
    if unknown:
        raise ValueError(f"Policy references absent annotation IDs: {sorted(unknown)}")
    for index, first in enumerate(retained):
        for second in retained[index + 1 :]:
            if (
                first["label"] != second["label"]
                and box_iou(xyxy(first["bbox"]), xyxy(second["bbox"])) >= 0.85
            ):
                issues.append(
                    f"Conflicting labels on overlapping boxes: {first['id']} {first['label']} / {second['id']} {second['label']}"
                )
            elif (
                overlap_review_iou is not None
                and box_iou(xyxy(first["bbox"]), xyxy(second["bbox"])) >= overlap_review_iou
            ):
                issues.append(
                    f"Ambiguous overlapping targets require review: {first['id']} / {second['id']}; not automatically merged."
                )
    if not retained and not verified_empty:
        issues.append("No usable piece annotations remain; not a verified empty-board example.")
    return retained, changes, issues


def equivalent_annotations(first, second, transform=0):
    """Require matching class/geometry as well as pixels before removing a near copy."""
    if len(first["annotations"]) != len(second["annotations"]):
        return False
    candidates = []
    width, height = second["size"]
    for annotation in second["annotations"]:
        x, y, w, h = annotation["bbox"]
        corners = [(x / width, y / height), ((x + w) / width, (y + h) / height)]
        points = []
        # Transform all corners to avoid swapping bounds incorrectly after quarter turns.
        for px, py in [
            (corners[0][0], corners[0][1]),
            (corners[0][0], corners[1][1]),
            (corners[1][0], corners[0][1]),
            (corners[1][0], corners[1][1]),
        ]:
            if transform >= 4:
                px = 1 - px
            for _ in range(transform % 4):
                px, py = py, 1 - px
            points.append((px, py))
        candidates.append(
            (
                annotation["label"],
                [
                    min(p[0] for p in points),
                    min(p[1] for p in points),
                    max(p[0] for p in points),
                    max(p[1] for p in points),
                ],
            )
        )
    used = set()
    for annotation in first["annotations"]:
        x, y, w, h = annotation["bbox"]
        target = [
            x / first["size"][0],
            y / first["size"][1],
            (x + w) / first["size"][0],
            (y + h) / first["size"][1],
        ]
        matches = [
            (box_iou(target, box), index)
            for index, (label, box) in enumerate(candidates)
            if label == annotation["label"] and index not in used
        ]
        overlap, index = max(matches, default=(0, -1))
        if overlap < 0.9:
            return False
        used.add(index)
    return True


def load_source(profile, policy):
    rows, source_hashes, image_hashes = [], {}, []
    overrides = policy.get("images", {})
    for split in SPLITS:
        annotation_path = profile.root / split / "_annotations.coco.json"
        source_hashes[split] = digest_bytes(annotation_path.read_bytes())
        coco = json.loads(annotation_path.read_text())
        categories = {
            item["id"]: profile.category_aliases.get(item["name"], item["name"])
            for item in coco["categories"]
        }
        by_image = defaultdict(list)
        for annotation in coco["annotations"]:
            by_image[annotation["image_id"]].append(annotation)
        if len({image["id"] for image in coco["images"]}) != len(coco["images"]) or len(
            {a["id"] for a in coco["annotations"]}
        ) != len(coco["annotations"]):
            raise ValueError(f"{split}: duplicate COCO IDs must be resolved before curation.")
        if set(by_image) - {image["id"] for image in coco["images"]}:
            raise ValueError(f"{split}: orphan annotation IDs")
        for item in coco["images"]:
            key = f"{split}/{item['file_name']}"
            path = resolve_image(profile.root, key)
            digest = digest_bytes(path.read_bytes())
            image_hashes.append((key, digest))
            decision = overrides.get(key, {})
            if decision and decision.get("sha256") != digest:
                raise ValueError(f"Reviewed image changed: {key}")
            row = {
                "key": key,
                "path": path,
                "source_id": item["id"],
                "original_split": split,
                "sha256": digest,
                "source_group": source_group(item["file_name"]),
                "capture_group": capture_group(source_group(item["file_name"])),
                "rotation": decision.get("rotation", "none"),
                "changes": [],
                "issues": [],
            }
            if decision.get("quarantine"):
                row["issues"].append(decision["quarantine"])
            try:
                with Image.open(path) as source:
                    source.load()
                    if source.getexif().get(274, 1) not in (None, 1):
                        raise ValueError("Unreviewed EXIF orientation")
                    image = source.convert("RGB")
                image = reviewed_rotation(image, row["rotation"])
                row["size"] = image.size
                row["pixel_sha256"] = digest_bytes(str(image.size).encode() + image.tobytes())
                if image.size != (item["width"], item["height"]):
                    row["issues"].append("Unresolved image/annotation dimension mismatch")
                if row["rotation"] != "none":
                    row["changes"].append(
                        {
                            "action": "reviewed_image_rotation",
                            "rotation": row["rotation"],
                            "reason": decision.get("reason", "Reviewed box overlays"),
                        }
                    )
                row["annotations"], changes, issues = clean_annotations(
                    by_image[item["id"]],
                    categories,
                    image.size,
                    drops=decision.get("drop_annotations"),
                    overlap_review_iou=policy.get("overlap_review_iou"),
                    verified_empty=decision.get("verified_empty", False),
                )
                row["changes"].extend(changes)
                row["issues"].extend(issues)
                if not row["issues"]:
                    row["thumb"], row["phashes"] = thumbnail_features(image)
            except (OSError, ValueError) as error:
                row["issues"].append(str(error))
                row.setdefault("annotations", [])
                row.setdefault("size", (item["width"], item["height"]))
            rows.append(row)
    if set(overrides) - {row["key"] for row in rows}:
        raise ValueError("Policy refers to images absent from this export.")
    snapshot = digest_bytes(json.dumps(sorted(image_hashes)).encode())
    if (
        policy.get("source_annotation_hashes") != source_hashes
        or policy.get("source_images_hash") != snapshot
    ):
        raise ValueError(
            "The raw snapshot differs from the reviewed policy. Create a new reviewed policy/version."
        )
    return rows, snapshot


def remove_copies(rows):
    candidates = [row for row in rows if not row["issues"]]
    by_pixels = defaultdict(list)
    for row in candidates:
        by_pixels[row["pixel_sha256"]].append(row)
    for members in by_pixels.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda row: row["key"])
        first = members[0]
        if any(not equivalent_annotations(first, row) for row in members[1:]):
            for row in members:
                row["issues"].append(
                    "Identical pixels have inconsistent annotations; requires review"
                )
        else:
            for row in members[1:]:
                row["duplicate_of"] = first["key"]
                row["changes"].append({"action": "identical_image_removed", "kept": first["key"]})
    active = [row for row in candidates if not row["issues"] and not row.get("duplicate_of")]
    pairs = near_pairs(active)
    for pair in pairs:
        first, second = active[pair["first"]], active[pair["second"]]
        if first.get("duplicate_of") or second.get("duplicate_of"):
            continue
        if (
            pair["correlation"] >= 0.998
            and pair["mae"] <= 2
            and equivalent_annotations(first, second, pair["transform"])
        ):
            second["duplicate_of"] = first["key"]
            second["changes"].append(
                {
                    "action": "near_identical_image_removed",
                    "kept": first["key"],
                    **{key: pair[key] for key in ("correlation", "mae", "hamming", "transform")},
                }
            )
    retained = [row for row in active if not row.get("duplicate_of")]
    # Recompute candidates after removals so split grouping uses retained-image indices.
    return retained, near_pairs(retained)


def public_row(row):
    return {key: value for key, value in row.items() if key not in ("path", "thumb", "phashes")}


def curate(profile, policy_path: Path, output: Path, report: Path):
    from .curation_report import write_review

    policy = json.loads(policy_path.read_text())
    if policy.get("format_version") != 1 or policy.get("dataset") != profile.name:
        raise ValueError("Policy version/dataset does not match the selected source.")
    if output.exists():
        raise ValueError(
            "Curated output already exists. Choose a new version; raw/curated directories are never overwritten."
        )
    output = output.resolve()
    report = report.resolve()
    raw = profile.root.resolve()
    if (report / "summary.json").exists():
        raise ValueError(
            "Report directory already belongs to a published version; choose a new --report."
        )
    if (
        output.is_relative_to(raw)
        or raw.is_relative_to(output)
        or report.is_relative_to(raw)
        or raw.is_relative_to(report)
        or report.is_relative_to(output)
        or output.is_relative_to(report)
    ):
        raise ValueError("Raw input, curated output and report directories must not overlap.")
    save_json(
        report / "prepared/audit.json",
        {"valid": False, "errors": ["Curation build has not been published."]},
    )
    rows, snapshot = load_source(profile, policy)
    retained, pairs = remove_copies(rows)
    split_info = assign_splits(
        retained,
        pairs,
        seed=policy.get("seed", 42),
        fixed_capture_splits=policy.get("fixed_capture_splits"),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        for split in SPLITS:
            folder = staging / split
            folder.mkdir()
            coco = {
                "info": {
                    "description": "Chass curated piece detection dataset; see provenance.json",
                    "version": output.name,
                },
                "licenses": [
                    {
                        "id": 1,
                        "name": profile.license,
                        "url": "https://creativecommons.org/licenses/by/4.0/",
                    }
                ],
                "categories": [
                    {"id": index, "name": name} for index, name in enumerate(CLASSES) if index
                ],
                "images": [],
                "annotations": [],
            }
            for row in retained:
                if row["split"] != split:
                    continue
                filename = Path(row["key"]).name
                if row["rotation"] != "none":
                    filename = str(Path(filename).with_suffix(".png"))
                if (folder / filename).exists():
                    raise ValueError(f"Output filename collision: {filename}")
                if row["rotation"] == "none":
                    shutil.copy2(row["path"], folder / filename)
                else:
                    with Image.open(row["path"]) as image:
                        reviewed_rotation(image, row["rotation"]).convert("RGB").save(
                            folder / filename
                        )
                image_id = len(coco["images"]) + 1
                row["output_file"] = f"{split}/{filename}"
                coco["images"].append(
                    {
                        "id": image_id,
                        "file_name": filename,
                        "width": row["size"][0],
                        "height": row["size"][1],
                        "license": 1,
                        "source_key": row["key"],
                        "capture_group": row["capture_group"],
                        "split_group": row["split_group"],
                    }
                )
                for annotation in row["annotations"]:
                    box = annotation["bbox"]
                    coco["annotations"].append(
                        {
                            "id": len(coco["annotations"]) + 1,
                            "image_id": image_id,
                            "category_id": CLASSES.index(annotation["label"]),
                            "bbox": box,
                            "area": box[2] * box[3],
                            "iscrowd": 0,
                            "segmentation": [],
                            "source_annotation_id": annotation["id"],
                        }
                    )
            save_json(folder / "_annotations.coco.json", coco)
        for readme in ("README.dataset.txt", "README.roboflow.txt"):
            if (raw / readme).exists():
                shutil.copy2(raw / readme, staging / readme)
        save_json(
            staging / "provenance.json",
            {
                "format_version": 1,
                "raw_snapshot": snapshot,
                "policy_sha256": digest_bytes(policy_path.read_bytes()),
                "policy": policy,
                "source": profile.source,
                "attribution": profile.attribution,
                "license": profile.license,
                "rows": [public_row(row) for row in rows],
            },
        )
        cleaned_profile = replace(
            profile,
            limitations=(
                "Curated export: original source split ratios are not retained; capture groups were re-split.",
                "Geometry and reviewed label errors were corrected; unreviewed semantic errors can remain.",
            ),
        )
        audit = prepare_dataset(staging, staging / "_audit", profile=cleaned_profile)
        if any(audit["splits"][split]["missing_classes"] for split in SPLITS):
            raise ValueError(
                "A curated split is missing classes; review capture grouping before training."
            )
        save_json(report / "build_audit.json", audit)
        shutil.rmtree(staging / "_audit")
        staging.rename(output)
        # Audit again using the published path so the manifest never points to a staging folder.
        audit = prepare_dataset(output, report / "prepared", profile=cleaned_profile)
        manifest_path = report / "prepared/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["splits_preserved"] = False
        manifest["curation"] = {
            "raw_snapshot": snapshot,
            "policy_sha256": digest_bytes(policy_path.read_bytes()),
            "version": output.name,
        }
        save_json(manifest_path, manifest)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    counts = Counter(change["action"] for row in rows for change in row["changes"])
    summary = {
        "format_version": 1,
        "dataset": profile.name,
        "version": output.name,
        "raw_images": len(rows),
        "kept_images": len(retained),
        "quarantined_images": sum(bool(row["issues"]) for row in rows),
        "removed_copy_images": sum(
            bool(row.get("duplicate_of")) and not row["issues"] for row in rows
        ),
        "kept_annotations": sum(len(row["annotations"]) for row in retained),
        "actions": dict(counts),
        "retained_actions": dict(
            Counter(change["action"] for row in retained for change in row["changes"])
        ),
        "splits": split_info,
        "near_candidate_pairs_grouped": len(pairs),
        "audit_valid": audit["valid"],
        "raw_snapshot": snapshot,
        "policy_sha256": digest_bytes(policy_path.read_bytes()),
        "manifest": str(manifest_path),
        "limitations": [
            "Not an exhaustive manual reannotation of every piece.",
            "Capture-date grouping is not proof of unseen physical-board-set isolation.",
            "Original Top Down baseline/test data is not merged or re-split.",
        ],
    }
    save_json(report / "summary.json", summary)
    save_json(report / "events.json", [public_row(row) for row in rows])
    save_json(
        report / "near_pairs.json",
        [
            {
                **pair,
                "first": retained[pair["first"]]["key"],
                "second": retained[pair["second"]]["key"],
            }
            for pair in pairs
        ],
    )
    write_review(report, rows, summary)
    return summary
