"""Apply reviewed annotation additions as an immutable manifest overlay."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from .data import CLASSES, read_manifest, save_json
from .metrics import box_iou


def apply_review(manifest, review):
    if manifest["fingerprint"] != review["source_fingerprint"]:
        raise ValueError("Label review targets a different dataset fingerprint.")
    updated = copy.deepcopy(manifest)
    by_id = {record["id"]: record for record in updated["records"]}
    for addition in review["additions"]:
        record = by_id[addition["image_id"]]
        if record["sha256"] != addition["image_sha256"] or not addition.get("reason"):
            raise ValueError("Each reviewed correction needs a matching image hash and reason.")
        box = addition["box"]
        if (
            len(box) != 4
            or not all(math.isfinite(value) for value in box)
            or not 0 <= box[0] < box[2] <= record["width"]
            or not 0 <= box[1] < box[3] <= record["height"]
            or addition["label"] not in CLASSES[1:]
        ):
            raise ValueError("Invalid reviewed annotation.")
        if any(box_iou(box, existing) >= 0.5 for existing in record["boxes"]):
            raise ValueError("Reviewed addition overlaps an existing annotation.")
        record["boxes"].append(box)
        record["labels"].append(CLASSES.index(addition["label"]))
        record["iscrowd"].append(0)
    updated["parent_fingerprint"] = manifest["fingerprint"]
    updated["fingerprint"] = hashlib.sha256(
        json.dumps({"classes": CLASSES, "records": updated["records"]}, sort_keys=True).encode()
    ).hexdigest()
    updated["label_review"] = review
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite a manifest.")
    save_json(
        args.output, apply_review(read_manifest(args.manifest), json.loads(args.review.read_text()))
    )
