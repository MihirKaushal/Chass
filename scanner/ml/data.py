from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from .datasets import TOP_DOWN, DatasetProfile

CLASSES = (
    "background",
    "black-bishop",
    "black-king",
    "black-knight",
    "black-pawn",
    "black-queen",
    "black-rook",
    "white-bishop",
    "white-king",
    "white-knight",
    "white-pawn",
    "white-queen",
    "white-rook",
)
SPLITS = ("train", "valid", "test")
DEFAULT_DATA = TOP_DOWN.root
DEFAULT_ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def source_group(filename: str) -> str:
    return re.sub(r"\.rf\.[^.]+\.[^.]+$", "", filename)


def resolve_image(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Image path escapes the dataset: {relative}")
    return path


def prepare_dataset(root: Path, output: Path, *, profile: DatasetProfile = TOP_DOWN) -> dict:
    """Audit the original COCO files; never rewrite images or reshuffle augmented splits."""
    import math

    root = root.resolve()
    errors, records, summary = [], [], {}
    source_splits, hash_splits = defaultdict(set), defaultdict(set)
    for split in SPLITS:
        annotation_path = root / split / "_annotations.coco.json"
        try:
            coco = json.loads(annotation_path.read_text())
        except (OSError, ValueError) as error:
            errors.append(f"{split}: cannot read COCO annotations: {error}")
            continue
        categories = {
            item["id"]: profile.category_aliases.get(item["name"], item["name"])
            for item in coco["categories"]
        }
        if len(categories) != len(coco["categories"]):
            errors.append(f"{split}: duplicate category IDs")
        unknown = set(categories.values()) - set(CLASSES) - set(profile.ignored_categories)
        if unknown:
            errors.append(f"{split}: unsupported categories: {sorted(unknown)}")
        annotations = defaultdict(list)
        seen_annotations = set()
        for annotation in coco["annotations"]:
            if annotation["id"] in seen_annotations:
                errors.append(f"{split}: duplicate annotation ID {annotation['id']}")
            seen_annotations.add(annotation["id"])
            annotations[annotation["image_id"]].append(annotation)
        seen_images, class_counts, groups = set(), Counter(), set()
        duplicate_boxes = 0
        piece_counts = []
        split_records = []
        for item in coco["images"]:
            image_id = item["id"]
            if image_id in seen_images:
                errors.append(f"{split}: duplicate image ID {image_id}")
            seen_images.add(image_id)
            relative = f"{split}/{item['file_name']}"
            path = resolve_image(root, relative)
            try:
                with Image.open(path) as image:
                    size = image.size
                    orientation = image.getexif().get(274, 1)
                    image.verify()
                if size != (item["width"], item["height"]):
                    raise ValueError("decoded dimensions do not match annotations")
                if orientation not in (None, 1):
                    raise ValueError(
                        "normalize EXIF orientation and transform labels before import"
                    )
            except (OSError, ValueError) as error:
                errors.append(f"{relative}: {error}")
                continue
            boxes, labels, crowds = [], [], []
            seen_boxes = set()
            for annotation in annotations[image_id]:
                name = categories.get(annotation["category_id"])
                box = annotation.get("bbox", [])
                if (
                    name not in CLASSES[1:]
                    or len(box) != 4
                    or not all(math.isfinite(v) for v in box)
                ):
                    errors.append(
                        f"{relative}: invalid category/bounding box for annotation {annotation['id']}"
                    )
                    continue
                x, y, width, height = box
                if (
                    min(width, height) <= 0
                    or min(x, y) < 0
                    or x + width > size[0] + 1e-4
                    or y + height > size[1] + 1e-4
                ):
                    errors.append(f"{relative}: out-of-bounds box {box}")
                    continue
                if annotation.get("iscrowd", 0) != 0:
                    errors.append(f"{relative}: annotate individual pieces, not crowd regions")
                    continue
                box_key = (name, *box)
                if box_key in seen_boxes:
                    duplicate_boxes += 1
                    errors.append(
                        f"{relative}: duplicate piece box for annotation {annotation['id']}"
                    )
                seen_boxes.add(box_key)
                boxes.append([x, y, x + width, y + height])
                labels.append(CLASSES.index(name))
                crowds.append(int(annotation.get("iscrowd", 0)))
                class_counts[name] += 1
            group = source_group(item["file_name"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            source_splits[group].add(split)
            hash_splits[digest].add(split)
            groups.add(group)
            piece_counts.append(len(boxes))
            split_records.append(
                {
                    "id": len(records) + len(split_records) + 1,
                    "split": split,
                    "file": relative,
                    "source_group": group,
                    "sha256": digest,
                    "width": size[0],
                    "height": size[1],
                    "boxes": boxes,
                    "labels": labels,
                    "iscrowd": crowds,
                }
            )
        orphaned = set(annotations) - seen_images
        if orphaned:
            errors.append(f"{split}: annotations reference missing image IDs {sorted(orphaned)}")
        summary[split] = {
            "declared_images": len(coco["images"]),
            "declared_annotations": len(coco["annotations"]),
            "images": len(split_records),
            "source_groups": len(groups),
            "annotations": sum(class_counts.values()),
            "classes": dict(sorted(class_counts.items())),
            "min_pieces": min(piece_counts, default=0),
            "max_pieces": max(piece_counts, default=0),
            "images_over_32_pieces": sum(count > 32 for count in piece_counts),
            "duplicate_piece_boxes": duplicate_boxes,
            "missing_classes": [name for name in CLASSES[1:] if not class_counts[name]],
        }
        if not split_records:
            errors.append(f"{split}: no usable images")
        records.extend(split_records)
    for kind, grouped in [("source filename", source_splits), ("image hash", hash_splits)]:
        for key, splits in grouped.items():
            if len(splits) > 1:
                errors.append(f"Leakage: {kind} {key} appears in {sorted(splits)}")
    fingerprint = hashlib.sha256(
        json.dumps({"classes": CLASSES, "records": records}, sort_keys=True).encode()
    ).hexdigest()
    report = {
        "valid": not errors,
        "dataset": profile.name,
        "source": profile.source,
        "attribution": profile.attribution,
        "license": profile.license,
        "category_aliases": profile.category_aliases,
        "errors": errors,
        "splits": summary,
        "total_images": len(records),
        "declared_total_images": sum(item["declared_images"] for item in summary.values()),
        "declared_total_annotations": sum(
            item["declared_annotations"] for item in summary.values()
        ),
        "source_groups": len(source_splits),
        "unique_image_hashes": len(hash_splits),
        "fingerprint": fingerprint,
        "scope": "12 foreground detection classes. Background is NOT a verified empty-square label.",
        "limitations": [
            *profile.limitations,
            "No verified board corners or 64-square ground truth is present.",
            "Source-name separation does not prove separation of capture sessions or physical chess sets.",
        ],
    }
    save_json(output / "audit.json", report)
    if errors:
        raise ValueError(
            f"Dataset audit failed ({len(errors)} issues); see {output / 'audit.json'}"
        )
    manifest = {
        "format_version": 1,
        "task": "piece_detection",
        "dataset_root": str(root),
        "classes": list(CLASSES),
        "fingerprint": fingerprint,
        "records": records,
        "dataset": profile.name,
        "source": profile.source,
        "attribution": profile.attribution,
        "license": profile.license,
        "category_aliases": profile.category_aliases,
        "splits_preserved": True,
    }
    save_json(output / "manifest.json", manifest)
    save_json(output / "classes.json", list(CLASSES))
    return report


def read_manifest(path: Path) -> dict:
    audit_path = path.parent / "audit.json"
    if audit_path.exists() and not json.loads(audit_path.read_text()).get("valid"):
        raise ValueError("The latest dataset audit failed; fix the data and run prepare again.")
    manifest = json.loads(path.read_text())
    if manifest.get("format_version") != 1 or manifest.get("classes") != list(CLASSES):
        raise ValueError("Unsupported manifest version or class mapping; run prepare again.")
    fingerprint = hashlib.sha256(
        json.dumps({"classes": CLASSES, "records": manifest["records"]}, sort_keys=True).encode()
    ).hexdigest()
    if fingerprint != manifest.get("fingerprint"):
        raise ValueError("Manifest fingerprint is invalid; run prepare again.")
    root = Path(manifest["dataset_root"])
    for record in manifest["records"]:
        image = resolve_image(root, record["file"])
        if hashlib.sha256(image.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(
                f"Image changed after preparation: {record['file']}; run prepare again."
            )
    return manifest


def collate_detection(batch):
    return tuple(zip(*batch, strict=True))


class CocoPieces:
    def __init__(self, manifest: dict, split: str, *, augment=False, root: Path | None = None):
        if split not in SPLITS:
            raise ValueError(f"Unknown split: {split}")
        if augment and split != "train":
            raise ValueError("Augmentation is only permitted for the training split.")
        self.records = [record for record in manifest["records"] if record["split"] == split]
        self.root = root or Path(manifest["dataset_root"])
        self.augment = augment

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        import random

        import torch
        from torchvision.transforms import functional as TF

        record = self.records[index]
        with Image.open(resolve_image(self.root, record["file"])) as source:
            image = source.convert("RGB")
        boxes = torch.tensor(record["boxes"], dtype=torch.float32).reshape(-1, 4)
        if self.augment:
            if random.random() < 0.5:
                image = TF.hflip(image)
                boxes[:, [0, 2]] = image.width - boxes[:, [2, 0]]
            image = TF.adjust_brightness(image, random.uniform(0.9, 1.1))
            image = TF.adjust_contrast(image, random.uniform(0.9, 1.1))
        target = {
            "boxes": boxes,
            "labels": torch.tensor(record["labels"], dtype=torch.int64),
            "image_id": torch.tensor(record["id"], dtype=torch.int64),
            "area": (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1]),
            "iscrowd": torch.tensor(record["iscrowd"], dtype=torch.int64),
        }
        return TF.to_tensor(image), target
