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
    def __init__(self, folder, *, batch_size=1):
        if batch_size not in (1, 2, 4):
            raise ValueError("Classifier batch size must be 1, 2, or 4.")
        self.batch_size = batch_size
        loading = time.perf_counter()
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
        shape = self.sessions["classifier"].get_inputs()[0].shape
        if isinstance(shape[0], int) and shape[0] != batch_size:
            raise ValueError("Export a dynamic-batch classifier before changing batch size.")
        self.load_ms = round((time.perf_counter() - loading) * 1000, 2)

    def detect(self, image):
        raw = self.sessions["detector"].run(
            None, {"image": resize_bilinear(image, self.config["input_size"])}
        )
        height, width = self.config["detector_size"]
        scale = np.asarray([image.width / width, image.height / height] * 2, dtype=np.float32)
        return [(score, label, box * scale) for score, label, box in detections(*raw, self.config)]

    def predict(self, image, *, rectified=False, tiled=False):
        started = time.perf_counter()
        timings = {}
        image = ImageOps.exif_transpose(image).convert("RGB")
        tensor = resize_bilinear(image, self.config["input_size"])
        timings["prepareMs"] = (time.perf_counter() - started) * 1000
        stamp = time.perf_counter()
        raw = self.sessions["detector"].run(None, {"image": tensor})
        timings["detectorMs"] = (time.perf_counter() - stamp) * 1000
        stamp = time.perf_counter()
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
        if tiled:
            # Experiment only: overlapping zooms recover detail without changing the trained input.
            w, h = round(image.width * 0.65), round(image.height * 0.65)
            for left, top in (
                (0, 0),
                (image.width - w, 0),
                (0, image.height - h),
                (image.width - w, image.height - h),
            ):
                for score, label, box in self.detect(image.crop((left, top, left + w, top + h))):
                    if score >= self.selection["threshold"]:
                        prediction["boxes"].append((box + [left, top, left, top]).tolist())
                        prediction["labels"].append(label)
                        prediction["scores"].append(score)
        prediction = resolve_duplicates(
            prediction, threshold=self.selection["threshold"], overlap=self.selection["overlap"]
        )
        timings["postprocessMs"] = (time.perf_counter() - stamp) * 1000
        prediction["detector_labels"] = prediction["labels"]
        prediction["labels"], prediction["classifier_scores"], prediction["alternatives"] = (
            [],
            [],
            [],
        )
        config = self.config["crop"]
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]
        timings["cropMs"], timings["classifierMs"] = 0, 0
        for offset in range(0, len(prediction["boxes"]), self.batch_size):
            stamp = time.perf_counter()
            tensors = []
            for box in prediction["boxes"][offset : offset + self.batch_size]:
                crop = piece_crop(image, box, context=config["context"], size=config["size"])
                pixels = np.asarray(crop, dtype=np.float32).transpose(2, 0, 1) / np.float32(255)
                tensors.append((pixels - mean) / std)
            tensor = np.ascontiguousarray(np.stack(tensors))
            timings["cropMs"] += (time.perf_counter() - stamp) * 1000
            stamp = time.perf_counter()
            probabilities = softmax(self.sessions["classifier"].run(None, {"image": tensor})[0])
            timings["classifierMs"] += (time.perf_counter() - stamp) * 1000
            for row in probabilities:
                choices = np.argsort(-row, kind="stable")[:3]
                prediction["labels"].append(int(choices[0]) + 1)
                prediction["classifier_scores"].append(float(row[choices[0]]))
                prediction["alternatives"].append(
                    [{"label": CLASSES[index + 1], "score": float(row[index])} for index in choices]
                )
        result = {
            "prediction": prediction,
            "pipeline": "combined",
            "runtime": "onnx",
            "classificationScoresAreCalibrated": False,
            "datasetFingerprint": self.selection["dataset_fingerprint"],
            "modelSha256": dict(self.config["sha256"]),
            "rectified": rectified,
        }
        if rectified:
            stamp = time.perf_counter()
            result.update(assign_squares(prediction, image.width, image.height))
            timings["squareMappingMs"] = (time.perf_counter() - stamp) * 1000
        result["inferenceMs"] = round((time.perf_counter() - started) * 1000)
        result["timings"] = {key: round(max(0, value), 2) for key, value in timings.items()}
        result["timings"]["proposals"] = len(prediction["boxes"])
        return result


def default_pipeline():
    return OnnxScannerPipeline(os.getenv("SCANNER_ONNX_DIR", "scanner/models/onnx"))
