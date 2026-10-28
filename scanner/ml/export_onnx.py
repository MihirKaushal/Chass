"""Export the validated weights for low-memory CPU serving, without retraining."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

from .data import CLASSES
from .inference import default_pipeline


class DetectorHead(torch.nn.Module):
    def __init__(self, detector):
        super().__init__()
        self.detector = detector

    def forward(self, batch):
        images, _ = self.detector.transform([batch[0]])
        features = list(self.detector.backbone(images.tensors).values())
        outputs = self.detector.head(features)
        anchors = self.detector.anchor_generator(images, features)[0]
        return outputs["bbox_regression"][0], outputs["cls_logits"][0], anchors


def export(output):
    output.mkdir(parents=True, exist_ok=False)
    pipeline = default_pipeline("cpu")
    size = pipeline.detector_checkpoint["config"].get("input_size", 320)
    crop = pipeline.classifier_checkpoint["config"]
    detector = DetectorHead(pipeline.detector).eval()
    samples = {
        "detector": (detector, torch.rand(1, 3, size, size), ["regression", "logits", "anchors"]),
        "classifier": (
            pipeline.classifier,
            torch.rand(1, 3, crop["size"], crop["size"]),
            ["logits"],
        ),
    }
    hashes = {}
    for name, (model, sample, outputs) in samples.items():
        path = output / f"{name}.onnx"
        with torch.inference_mode():
            torch.onnx.export(
                model,
                (sample,),
                str(path),
                input_names=["image"],
                output_names=outputs,
                opset_version=17,
                dynamo=False,
                external_data=False,
            )
            expected = model(sample)
        onnx.checker.check_model(str(path))
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        actual = session.run(None, {"image": sample.numpy()})
        expected = expected if isinstance(expected, tuple) else (expected,)
        for reference, result in zip(expected, actual, strict=True):
            np.testing.assert_allclose(reference.numpy(), result, rtol=1e-3, atol=3e-4)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "format_version": 1,
        "selection": pipeline.selection,
        "sha256": hashes,
        "classes": list(CLASSES),
        "input_size": size,
        "crop": crop,
        "detector_size": list(pipeline.detector.transform.fixed_size),
        "box_weights": list(pipeline.detector.box_coder.weights),
        "box_clip": pipeline.detector.box_coder.bbox_xform_clip,
        "score_threshold": pipeline.detector.score_thresh,
        "nms_threshold": pipeline.detector.nms_thresh,
        "topk_candidates": pipeline.detector.topk_candidates,
        "detections_per_image": pipeline.detector.detections_per_img,
        "export_versions": {
            "torch": torch.__version__,
            "onnx": onnx.__version__,
            "onnxruntime": ort.__version__,
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Exported and checked floating-point graphs in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args().output)
