from __future__ import annotations

import contextlib
import io
import math
import time
from collections import Counter

import torch

from .box_geometry import box_iou as box_iou
from .data import CLASSES


def operating_metrics(predictions: list[dict], records: list[dict], threshold: float) -> dict:
    counters = {name: Counter(tp=0, fp=0, fn=0, support=0) for name in CLASSES[1:]}
    exact = 0
    by_id = {item["image_id"]: item for item in predictions}
    for record in records:
        prediction = by_id[record["id"]]
        gt = [
            (box, label)
            for box, label, crowd in zip(
                record["boxes"], record["labels"], record["iscrowd"], strict=True
            )
            if not crowd
        ]
        matched = set()
        image_fp = 0
        for box, label, score in sorted(
            zip(prediction["boxes"], prediction["labels"], prediction["scores"], strict=True),
            key=lambda item: -item[2],
        ):
            if score < threshold:
                continue
            candidates = [
                (box_iou(box, target), index)
                for index, (target, category) in enumerate(gt)
                if category == label and index not in matched
            ]
            overlap, index = max(candidates, default=(0, -1))
            counter = counters[CLASSES[label]]
            if overlap >= 0.5:
                matched.add(index)
                counter["tp"] += 1
            else:
                counter["fp"] += 1
                image_fp += 1
        for index, (_, label) in enumerate(gt):
            counter = counters[CLASSES[label]]
            counter["support"] += 1
            if index not in matched:
                counter["fn"] += 1
        exact += int(len(matched) == len(gt) and not image_fp)

    def scores(counts):
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        return {
            **{key: counts[key] for key in ("tp", "fp", "fn", "support")},
            "precision": precision,
            "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        }

    total = sum(counters.values(), Counter())
    return {
        **scores(total),
        "threshold": threshold,
        "matching_iou": 0.5,
        "exact_detection_images": exact,
        "images": len(records),
        "exact_detection_image_rate": exact / len(records) if records else 0.0,
        "per_class": {name: scores(counter) for name, counter in counters.items()},
        "note": "Exact detection requires every annotated piece matched at IoU >= 0.5 and no extra detections. This is NOT exact-board accuracy.",
    }


def coco_metrics(predictions: list[dict], records: list[dict]) -> dict:
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    annotations, detections = [], []
    for record in records:
        for box, label, crowd in zip(
            record["boxes"], record["labels"], record["iscrowd"], strict=True
        ):
            x1, y1, x2, y2 = box
            annotations.append(
                {
                    "id": len(annotations) + 1,
                    "image_id": record["id"],
                    "category_id": label,
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "area": (x2 - x1) * (y2 - y1),
                    "iscrowd": crowd,
                }
            )
    for prediction in predictions:
        for box, label, score in zip(
            prediction["boxes"], prediction["labels"], prediction["scores"], strict=True
        ):
            x1, y1, x2, y2 = box
            detections.append(
                {
                    "image_id": prediction["image_id"],
                    "category_id": label,
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "score": score,
                }
            )
    coco = COCO()
    coco.dataset = {
        "info": {},
        "images": [{key: record[key] for key in ("id", "width", "height")} for record in records],
        "annotations": annotations,
        "categories": [{"id": index, "name": name} for index, name in enumerate(CLASSES) if index],
    }
    with contextlib.redirect_stdout(io.StringIO()):
        coco.createIndex()
        if detections:
            detected = coco.loadRes(detections)
        else:
            detected = COCO()
            detected.dataset = {**coco.dataset, "annotations": []}
            detected.createIndex()
        evaluation = COCOeval(coco, detected, "bbox")
        evaluation.params.imgIds = [record["id"] for record in records]
        evaluation.evaluate()
        evaluation.accumulate()
        evaluation.summarize()
    per_class = {}
    for index, name in enumerate(CLASSES[1:]):
        values = evaluation.eval["precision"][0, :, index, 0, -1]
        values = values[values > -1]
        per_class[name] = float(values.mean()) if len(values) else None
    return {
        "map50": float(evaluation.stats[1]),
        "map50_95": float(evaluation.stats[0]),
        "per_class_ap50": per_class,
    }


@torch.inference_mode()
def collect_predictions(model, dataset, device, batch_size=8):
    from torch.utils.data import DataLoader

    from .data import collate_detection, resize_boxes

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_detection)
    model.eval()
    predictions = []
    records = {record["id"]: record for record in dataset.records}
    started = time.perf_counter()
    for images, targets in loader:
        output = model([image.to(device) for image in images])
        for image, target, result in zip(images, targets, output, strict=True):
            record = records[int(target["image_id"])]
            result["boxes"] = resize_boxes(
                result["boxes"],
                (image.shape[-1], image.shape[-2]),
                (record["width"], record["height"]),
            )
            predictions.append(
                {
                    "image_id": int(target["image_id"]),
                    **{key: value.detach().cpu().tolist() for key, value in result.items()},
                }
            )
    elapsed = time.perf_counter() - started
    if any(not math.isfinite(score) for item in predictions for score in item["scores"]):
        raise ValueError("The model produced non-finite confidence scores.")
    return predictions, {
        "seconds": elapsed,
        "mean_ms_per_image": elapsed * 1000 / max(1, len(dataset)),
        "device": str(device),
        "batch_size": batch_size,
    }
