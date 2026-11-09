"""Assemble manually reviewed boards with physical-set holdouts and exact photo hashes."""

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

from .data import save_json
from .geometry import square_metrics
from .square_benchmark import evaluate


def collect(exports, photos, groups):
    records, splits_by_set, photo_index, splits_by_source = {}, {}, {}, {}
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
            for source in (
                f"session:{group['session']}",
                f"source:{group['source_group']}" if group.get("source_group") else None,
            ):
                if source and splits_by_source.setdefault(source, group["split"]) != group["split"]:
                    raise ValueError(
                        "A capture session or source group cannot cross collection splits."
                    )
            if (
                record.get("verification") == "user_reviewed_not_independently_audited"
                and group.get("labels_checked") is not True
            ):
                raise ValueError(
                    "Recheck exported labels against the photo and set labels_checked=true."
                )
            entry = {
                **record,
                "image_id": digest,
                "file": photo_index[digest],
                "board_set": group["board_set"],
                "session": group["session"],
                "split": group["split"],
                "verification": "collection_checked",
                "source_group": group.get("source_group"),
            }
            if digest in records and any(
                records[digest][field] != entry[field]
                for field in ("board", "board_set", "session", "split", "source_group")
            ):
                raise ValueError("Conflicting labels for the same photo; resolve them manually.")
            records.setdefault(digest, entry)
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
    predictions, latencies = [], []
    for record in records:
        photo = (photos / record["file"]).resolve()
        if not photo.is_relative_to(photos.resolve()):
            raise ValueError("Photo must be inside the collection directory.")
        if hashlib.sha256(photo.read_bytes()).hexdigest() != record["image_sha256"]:
            raise ValueError("Collection photo changed after verification.")
        with Image.open(photo) as image:
            started = time.perf_counter()
            result = pipeline.predict(image, rectified=True)
            latencies.append((time.perf_counter() - started) * 1000)
        predictions.append(
            {
                "image_id": record["image_id"],
                "image_sha256": record["image_sha256"],
                "board": result["board"],
                "reviewSquares": result["reviewSquares"],
                "inference_ms": result["inferenceMs"],
            }
        )
    return {
        "split": split,
        "model_sha256": pipeline.config["sha256"],
        "metrics": evaluate({"records": predictions}, {"records": records}),
        "records": predictions,
        "runtime": {
            "platform": platform.platform(),
            "model_load_ms": pipeline.load_ms,
            "inference_ms": latencies,
            "includes_network_or_service_wake": False,
        },
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
