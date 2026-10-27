"""Resolve overlapping piece proposals without using ground-truth labels."""

from __future__ import annotations

import math

from .metrics import box_iou


def resolve_duplicates(prediction, *, threshold=0.25, overlap=0.6):
    if not 0 <= threshold <= 1 or not 0 < overlap <= 1:
        raise ValueError("Invalid confidence or overlap threshold.")
    boxes, labels, scores = prediction["boxes"], prediction["labels"], prediction["scores"]
    if not len(boxes) == len(labels) == len(scores):
        raise ValueError("Prediction arrays must have the same length.")
    for box, score, label in zip(boxes, scores, labels, strict=True):
        if (
            len(box) != 4
            or not all(math.isfinite(v) for v in box)
            or box[2] <= box[0]
            or box[3] <= box[1]
            or not math.isfinite(score)
            or not 0 <= score <= 1
            or not isinstance(label, int)
            or not 1 <= label <= 12
        ):
            raise ValueError("Invalid piece proposal.")
    keep, groups = [], []
    for index in sorted(range(len(scores)), key=lambda i: (-scores[i], i)):
        if scores[index] < threshold:
            continue
        owner = next(
            (
                j
                for j, selected in enumerate(keep)
                if box_iou(boxes[index], boxes[selected]) >= overlap
            ),
            None,
        )
        if owner is None:
            keep.append(index)
            groups.append([index])
        else:
            groups[owner].append(index)
    result = {key: prediction[key] for key in ("image_id",) if key in prediction}
    for key in (
        "boxes",
        "labels",
        "scores",
        "classifier_scores",
        "alternatives",
        "detector_labels",
    ):
        if key in prediction:
            if len(prediction[key]) != len(scores):
                raise ValueError(f"Prediction {key} must align with its boxes.")
            result[key] = [prediction[key][i] for i in keep]
    result["duplicate_counts"] = [len(group) - 1 for group in groups]
    return result
