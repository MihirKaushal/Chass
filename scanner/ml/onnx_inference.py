"""CPU-only serving without importing Torch. Keep image processing equivalent to training."""

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import ImageOps

from .crops import piece_crop
from .data import CLASSES
from .geometry import assign_squares
from .postprocess import resolve_duplicates


def resize_bilinear(image, size):
    # PyTorch interpolate: half-pixel centers, align_corners=False, no antialiasing.
    pixels = np.asarray(image)
    height, width = pixels.shape[:2]
    x = np.maximum((np.arange(size, dtype=np.float32) + 0.5) * (width / size) - 0.5, 0)
    y = np.maximum((np.arange(size, dtype=np.float32) + 0.5) * (height / size) - 0.5, 0)
    x0, y0 = x.astype(int), y.astype(int)
    x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
    wx, wy = (x - x0).astype(np.float32)[None, :, None], (y - y0).astype(np.float32)[:, None, None]
    # Convert only sampled pixels, not a full high-resolution float image.
    top = (pixels[y0[:, None], x0].astype(np.float32) / 255) * (1 - wx) + (
        pixels[y0[:, None], x1].astype(np.float32) / 255
    ) * wx
    bottom = (pixels[y1[:, None], x0].astype(np.float32) / 255) * (1 - wx) + (
        pixels[y1[:, None], x1].astype(np.float32) / 255
    ) * wx
    return np.ascontiguousarray((top * (1 - wy) + bottom * wy).transpose(2, 0, 1)[None])


def softmax(logits):
    values = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return values / values.sum(axis=-1, keepdims=True)


def nms(boxes, scores, threshold):
    order = np.argsort(-scores, kind="stable")
    keep = []
    area = np.maximum(boxes[:, 2:] - boxes[:, :2], 0).prod(axis=1)
    while order.size:
        chosen = int(order[0])
        keep.append(chosen)
        rest = order[1:]
        intersection = np.maximum(
            np.minimum(boxes[chosen, 2:], boxes[rest, 2:])
            - np.maximum(boxes[chosen, :2], boxes[rest, :2]),
            0,
        ).prod(axis=1)
        union = area[chosen] + area[rest] - intersection
        iou = np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)
        order = rest[iou <= threshold]
    return keep


def detections(regression, logits, anchors, config):
    widths = anchors[:, 2] - anchors[:, 0]
    heights = anchors[:, 3] - anchors[:, 1]
    dx, dy, dw, dh = (regression / np.asarray(config["box_weights"], dtype=np.float32)).T
    center_x = anchors[:, 0] + widths * 0.5 + dx * widths
    center_y = anchors[:, 1] + heights * 0.5 + dy * heights
    pred_w = np.exp(np.minimum(dw, config["box_clip"])) * widths
    pred_h = np.exp(np.minimum(dh, config["box_clip"])) * heights
    boxes = np.stack(
        (
            center_x - pred_w * 0.5,
            center_y - pred_h * 0.5,
            center_x + pred_w * 0.5,
            center_y + pred_h * 0.5,
        ),
        axis=1,
    )
    height, width = config["detector_size"]
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, width)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, height)
    probabilities = softmax(logits)
    candidates = []
    for label in range(1, len(CLASSES)):
        scores = probabilities[:, label]
        indices = np.flatnonzero(scores > config["score_threshold"])
        indices = indices[np.argsort(-scores[indices], kind="stable")[: config["topk_candidates"]]]
        for chosen in nms(boxes[indices], scores[indices], config["nms_threshold"]):
            index = indices[chosen]
            candidates.append((float(scores[index]), label, boxes[index]))
    candidates.sort(key=lambda item: -item[0])
    candidates = candidates[: config["detections_per_image"]]
    return candidates


class OnnxScannerPipeline:
    def __init__(self, folder):
        folder = Path(folder)
        self.config = json.loads((folder / "manifest.json").read_text())
        if self.config["format_version"] != 1 or self.config["classes"] != list(CLASSES):
            raise ValueError("Unsupported scanner model manifest.")
        self.selection = self.config["selection"]
        if self.selection["pipeline"] != "combined":
            raise ValueError("The public scanner requires the validated combined pipeline.")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        self.sessions = {}
        for name in ("detector", "classifier"):
            path = folder / f"{name}.onnx"
            if hashlib.sha256(path.read_bytes()).hexdigest() != self.config["sha256"][name]:
                raise ValueError(f"{name} checksum does not match its deployment manifest.")
            self.sessions[name] = ort.InferenceSession(
                str(path), sess_options=options, providers=["CPUExecutionProvider"]
            )

    def predict(self, image, *, rectified=False):
        started = time.perf_counter()
        image = ImageOps.exif_transpose(image).convert("RGB")
        raw = self.sessions["detector"].run(
            None, {"image": resize_bilinear(image, self.config["input_size"])}
        )
        selected = [
            item for item in detections(*raw, self.config) if item[0] >= self.selection["threshold"]
        ]
        height, width = self.config["detector_size"]
        scale = np.asarray([image.width / width, image.height / height] * 2, dtype=np.float32)
        prediction = {
            "boxes": [(box * scale).tolist() for _, _, box in selected],
            "labels": [label for _, label, _ in selected],
            "scores": [score for score, _, _ in selected],
        }
        prediction = resolve_duplicates(
            prediction, threshold=self.selection["threshold"], overlap=self.selection["overlap"]
        )
        prediction["detector_labels"] = prediction["labels"]
        prediction["labels"], prediction["classifier_scores"], prediction["alternatives"] = (
            [],
            [],
            [],
        )
        config = self.config["crop"]
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]
        # One crop at a time bounds peak memory independently of the piece count.
        for box in prediction["boxes"]:
            crop = piece_crop(image, box, context=config["context"], size=config["size"])
            pixels = np.asarray(crop, dtype=np.float32).transpose(2, 0, 1) / np.float32(255)
            tensor = np.ascontiguousarray(((pixels - mean) / std)[None])
            probabilities = softmax(self.sessions["classifier"].run(None, {"image": tensor})[0])[0]
            choices = np.argsort(-probabilities, kind="stable")[:3]
            prediction["labels"].append(int(choices[0]) + 1)
            prediction["classifier_scores"].append(float(probabilities[choices[0]]))
            prediction["alternatives"].append(
                [
                    {"label": CLASSES[index + 1], "score": float(probabilities[index])}
                    for index in choices
                ]
            )
        result = {
            "prediction": prediction,
            "pipeline": "combined",
            "runtime": "onnx",
            "classificationScoresAreCalibrated": False,
            "datasetFingerprint": self.selection["dataset_fingerprint"],
            "rectified": rectified,
        }
        if rectified:
            result.update(assign_squares(prediction, image.width, image.height))
        result["inferenceMs"] = round((time.perf_counter() - started) * 1000)
        return result


def default_pipeline():
    return OnnxScannerPipeline(os.getenv("SCANNER_ONNX_DIR", "scanner/models/onnx"))
