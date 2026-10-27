"""Load a validation-selected detector/classifier pipeline for local experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
from PIL import Image, ImageOps

from .classifier import crop_transform, load_classifier
from .crops import piece_crop
from .data import CLASSES, DEFAULT_ARTIFACTS, detector_tensor, resize_boxes, save_json
from .geometry import assign_squares
from .model import choose_device, load_checkpoint
from .postprocess import resolve_duplicates


class ScannerPipeline:
    def __init__(self, selection_path, detector_path, classifier_path, device="auto"):
        self.selection = json.loads(selection_path.read_text())
        if self.selection["pipeline"] not in {
            "baseline",
            "duplicates_only",
            "classifier_only",
            "combined",
        }:
            raise ValueError("Unknown selected scanner pipeline.")
        self.device = choose_device(device)
        torch.set_num_threads(4)
        for key, path in (
            ("detector_sha256", detector_path),
            ("classifier_sha256", classifier_path),
        ):
            if hashlib.sha256(path.read_bytes()).hexdigest() != self.selection[key]:
                raise ValueError("Model checksum differs from the validated pipeline selection.")
        self.detector, self.detector_checkpoint = load_checkpoint(detector_path, self.device)
        self.classifier, self.classifier_checkpoint = load_classifier(classifier_path, self.device)
        for checkpoint in (self.detector_checkpoint, self.classifier_checkpoint):
            if checkpoint["dataset_fingerprint"] != self.selection["dataset_fingerprint"]:
                raise ValueError("Selected models were trained on different datasets.")
        self.transform = crop_transform()

    @torch.inference_mode()
    def predict(self, image, *, rectified=False):
        started = time.perf_counter()
        image = ImageOps.exif_transpose(image).convert("RGB")
        input_size = self.detector_checkpoint["config"].get("input_size", 320)
        raw = self.detector([detector_tensor(image, input_size).to(self.device)])[0]
        boxes = resize_boxes(raw["boxes"].cpu(), (input_size, input_size), image.size).tolist()
        threshold, overlap = self.selection["threshold"], self.selection["overlap"]
        selected = [i for i, score in enumerate(raw["scores"].tolist()) if score >= threshold]
        prediction = {
            "boxes": [boxes[i] for i in selected],
            "labels": [int(raw["labels"][i].item()) for i in selected],
            "scores": [float(raw["scores"][i].item()) for i in selected],
        }
        # Suppression uses only detector score/geometry, so doing it before crops saves inference.
        if self.selection["pipeline"] in {"duplicates_only", "combined"}:
            prediction = resolve_duplicates(prediction, threshold=threshold, overlap=overlap)
        if self.selection["pipeline"] in {"classifier_only", "combined"}:
            config = self.classifier_checkpoint["config"]
            prediction["detector_labels"] = list(prediction["labels"])
            prediction["labels"], prediction["classifier_scores"], prediction["alternatives"] = (
                [],
                [],
                [],
            )
            for offset in range(0, len(prediction["boxes"]), 48):
                crops = [
                    self.transform(
                        piece_crop(image, box, context=config["context"], size=config["size"])
                    )
                    for box in prediction["boxes"][offset : offset + 48]
                ]
                probabilities = self.classifier(torch.stack(crops).to(self.device)).softmax(1).cpu()
                scores, labels = probabilities.topk(3, dim=1)
                for values, classes in zip(scores.tolist(), labels.tolist(), strict=True):
                    prediction["labels"].append(classes[0] + 1)
                    prediction["classifier_scores"].append(values[0])
                    prediction["alternatives"].append(
                        [
                            {"label": CLASSES[label + 1], "score": score}
                            for label, score in zip(classes, values, strict=True)
                        ]
                    )
        result = {
            "prediction": prediction,
            "pipeline": self.selection["pipeline"],
            "classificationScoresAreCalibrated": False,
            "datasetFingerprint": self.selection["dataset_fingerprint"],
            "rectified": rectified,
        }
        if rectified:
            result.update(assign_squares(prediction, image.width, image.height))
        result["inferenceMs"] = round((time.perf_counter() - started) * 1000)
        return result


def default_pipeline(device="auto"):
    return ScannerPipeline(
        Path(
            os.environ.get(
                "SCANNER_SELECTION", DEFAULT_ARTIFACTS / "improvements/experiment-v1/selection.json"
            )
        ),
        Path(os.environ.get("SCANNER_DETECTOR", DEFAULT_ARTIFACTS / "chess-v2-baseline/best.pt")),
        Path(
            os.environ.get("SCANNER_CLASSIFIER", DEFAULT_ARTIFACTS / "crop-classifier-v1/best.pt")
        ),
        device,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--rectified",
        action="store_true",
        help="Photo is cropped to the playing grid, White at bottom.",
    )
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_ARTIFACTS / "improved-prediction.json"
    )
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Use the path to an existing JPG/PNG/WebP photo, not a placeholder path.")
    with Image.open(args.image) as image:
        result = default_pipeline(args.device).predict(image, rectified=args.rectified)
    save_json(args.output, result)
    print(f"Saved {len(result['prediction']['boxes'])} piece proposals to {args.output}")
