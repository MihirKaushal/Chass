"""Original-resolution piece crops, preserving the manifest's image/group splits."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageOps

from .data import read_manifest, resolve_image, save_json


def piece_crop(image, box, *, context=0.15, size=160):
    if (
        len(box) != 4
        or not all(math.isfinite(v) for v in box)
        or box[2] <= box[0]
        or box[3] <= box[1]
        or not 0 <= context <= 1
        or not 32 <= size <= 512
    ):
        raise ValueError("Invalid crop box, context, or size.")
    width, height = box[2] - box[0], box[3] - box[1]
    bounds = (
        max(0, math.floor(box[0] - width * context)),
        max(0, math.floor(box[1] - height * context)),
        min(image.width, math.ceil(box[2] + width * context)),
        min(image.height, math.ceil(box[3] + height * context)),
    )
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError("The crop does not intersect the image.")
    return ImageOps.pad(
        image.convert("RGB").crop(bounds),
        (size, size),
        method=Image.Resampling.BILINEAR,
        color=(127, 127, 127),
    )


def prepare_crops(manifest_path, output, *, size=160, context=0.15):
    manifest = read_manifest(manifest_path)
    spec = {
        "dataset_fingerprint": manifest["fingerprint"],
        "size": size,
        "context": context,
        "format_version": 1,
    }
    index_path = output / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
        digest = hashlib.sha256(
            json.dumps(
                {key: value for key, value in index.items() if key != "fingerprint"}, sort_keys=True
            ).encode()
        ).hexdigest()
        if index.get("fingerprint") != digest:
            raise ValueError("Crop cache metadata was modified; rebuild in a new directory.")
        if any(index.get(key) != value for key, value in spec.items()):
            raise ValueError("Crop cache belongs to another dataset or crop configuration.")
        if not all((output / record["crop"]).is_file() for record in index["records"]):
            raise ValueError("Incomplete crop cache; create a new cache directory.")
        return index
    records = []
    for number, record in enumerate(manifest["records"]):
        with Image.open(resolve_image(Path(manifest["dataset_root"]), record["file"])) as original:
            image = original.convert("RGB")
            for position, (box, label, crowd) in enumerate(
                zip(record["boxes"], record["labels"], record["iscrowd"], strict=True)
            ):
                if crowd:
                    continue
                relative = f"{record['split']}/{record['id']}-{position}.jpg"
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                piece_crop(image, box, context=context, size=size).save(path, quality=95)
                records.append(
                    {
                        "crop": relative,
                        "label": label,
                        "split": record["split"],
                        "image_id": record["id"],
                        "box_index": position,
                        "split_group": record.get("split_group"),
                        "source_sha256": record["sha256"],
                    }
                )
        if number % 200 == 0:
            print(f"Cached crops from {number + 1}/{len(manifest['records'])} images", flush=True)
    index = {**spec, "records": records}
    index["fingerprint"] = hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest()
    save_json(index_path, index)
    return index
