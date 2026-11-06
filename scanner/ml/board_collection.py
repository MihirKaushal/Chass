"""Assemble manually reviewed boards with physical-set holdouts and exact photo hashes."""

import argparse
import hashlib
import json
from pathlib import Path

from .data import save_json
from .geometry import square_metrics
from .square_benchmark import evaluate


def collect(exports, photos, groups):
    records, splits_by_set, photo_index = {}, {}, {}
    for photo in sorted(photos.rglob("*")):
        if photo.is_file() and photo.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            digest = hashlib.sha256(photo.read_bytes()).hexdigest()
            photo_index.setdefault(digest, str(photo.relative_to(photos)))
    for export in exports:
        for record in json.loads(export.read_text())["records"]:
            digest = record.get("image_sha256")
            if digest not in photo_index:
                raise ValueError(
                    "Reviewed labels require the exact prepared photo, not the original upload."
                )
            if record.get("verified") is not True or record.get("orientation") != "white_bottom":
                raise ValueError("Only manually verified, White-at-bottom boards are accepted.")
            square_metrics([record["board"]], [record["board"]])
            group = groups.get(digest, {})
            if (
                group.get("split") not in {"train", "valid", "test"}
                or not group.get("board_set")
                or not group.get("session")
            ):
                raise ValueError(
                    "Assign a physical board_set, capture session and split to every photo hash."
                )
            previous = splits_by_set.setdefault(group["board_set"], group["split"])
            if previous != group["split"]:
                raise ValueError("The same physical chess set cannot cross collection splits.")
            entry = {
                **record,
                "image_id": digest,
                "file": photo_index[digest],
                "board_set": group["board_set"],
                "session": group["session"],
                "split": group["split"],
            }
            if digest in records and records[digest] != entry:
                raise ValueError("Conflicting labels for the same photo; resolve them manually.")
            records[digest] = entry
    if not records:
        raise ValueError("No verified boards were supplied.")
    return {"format_version": 1, "records": sorted(records.values(), key=lambda r: r["image_id"])}


def score(collection, photos, models, split):
    from PIL import Image

    from .onnx_inference import OnnxScannerPipeline

    records = [record for record in collection["records"] if record["split"] == split]
    if not records:
        raise ValueError("No verified boards in the requested split.")
    pipeline = OnnxScannerPipeline(models)
    predictions = []
    for record in records:
        photo = (photos / record["file"]).resolve()
        if not photo.is_relative_to(photos.resolve()):
            raise ValueError("Photo must be inside the collection directory.")
        if hashlib.sha256(photo.read_bytes()).hexdigest() != record["image_sha256"]:
            raise ValueError("Collection photo changed after verification.")
        with Image.open(photo) as image:
            result = pipeline.predict(image, rectified=True)
        predictions.append(
            {
                "image_id": record["image_id"],
                "image_sha256": record["image_sha256"],
                "board": result["board"],
            }
        )
    return {
        "split": split,
        "model_sha256": pipeline.config["sha256"],
        "metrics": evaluate({"records": predictions}, {"records": records}),
        "records": predictions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "score"])
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--exports", type=Path, nargs="+")
    parser.add_argument("--groups", type=Path)
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--models", type=Path, default=Path("scanner/models/onnx"))
    parser.add_argument("--split", choices=["train", "valid", "test"], default="valid")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output path to preserve evaluation history.")
    if args.action == "collect":
        if not args.exports or not args.groups:
            parser.error("collect requires --exports and --groups")
        result = collect(args.exports, args.photos, json.loads(args.groups.read_text()))
    else:
        if not args.collection:
            parser.error("score requires --collection")
        result = score(
            json.loads(args.collection.read_text()), args.photos, args.models, args.split
        )
        result["collection_sha256"] = hashlib.sha256(args.collection.read_bytes()).hexdigest()
    save_json(args.output, result)
