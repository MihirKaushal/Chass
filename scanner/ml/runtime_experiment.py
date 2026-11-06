"""Reproducible CPU/quantization experiments. Never replaces deployment weights."""

import argparse
import hashlib
import json
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .data import read_manifest, resolve_image, save_json


def quantize(source, output, cache, samples_per_class=16):
    from onnxruntime.quantization import (
        CalibrationDataReader,
        QuantFormat,
        QuantType,
        quantize_static,
    )
    from onnxruntime.quantization.shape_inference import quant_pre_process

    if output.exists():
        raise ValueError("Use a fresh output directory.")
    index = json.loads((cache / "index.json").read_text())
    config = json.loads((source / "manifest.json").read_text())
    if index["dataset_fingerprint"] != config["selection"]["dataset_fingerprint"]:
        raise ValueError("Calibration and model datasets differ.")
    counts, records = {}, []
    for record in index["records"]:
        label = record["label"]
        if record["split"] == "train" and counts.get(label, 0) < samples_per_class:
            records.append(record)
            counts[label] = counts.get(label, 0) + 1
    if len(counts) != 12:
        raise ValueError("Calibration requires all twelve classes from training only.")
    output.mkdir(parents=True)
    for name in ("detector.onnx", "manifest.json"):
        shutil.copy2(source / name, output / name)
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
    std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.iterator = iter(records)

        def get_next(self):
            record = next(self.iterator, None)
            if record is None:
                return None
            with Image.open(cache / record["crop"]) as photo:
                pixels = np.asarray(photo.convert("RGB"), dtype=np.float32).transpose(2, 0, 1) / 255
            return {"image": np.ascontiguousarray(((pixels - mean) / std)[None])}

    prepared = output / "classifier-prepared.onnx"
    quant_pre_process(str(source / "classifier.onnx"), str(prepared), skip_symbolic_shape=True)
    quantize_static(
        str(prepared),
        str(output / "classifier.onnx"),
        Reader(),
        quant_format=QuantFormat.QDQ,
        per_channel=True,
        activation_type=QuantType.QInt8,
        weight_type=QuantType.QInt8,
        op_types_to_quantize=["Conv", "Gemm", "MatMul"],
    )
    prepared.unlink()
    config["sha256"]["classifier"] = hashlib.sha256(
        (output / "classifier.onnx").read_bytes()
    ).hexdigest()
    config["experiment"] = {"precision": "classifier-int8-qdq", "calibration_split": "train"}
    save_json(output / "manifest.json", config)
    save_json(
        output / "calibration.json",
        {
            "split": "train",
            "samples": len(records),
            "crop_fingerprint": index["fingerprint"],
            "crops": [record["crop"] for record in records],
        },
    )


def worker(models, manifest_path, output, limit, batch, tiled=False):
    from .onnx_inference import OnnxScannerPipeline

    manifest = read_manifest(manifest_path)
    records = [r for r in manifest["records"] if r["split"] == "valid"]
    if limit:
        # Spread timing samples across the split, not just adjacent captures.
        records = [
            records[i]
            for i in np.linspace(0, len(records) - 1, min(limit, len(records)), dtype=int)
        ]
    pipeline = OnnxScannerPipeline(models, batch_size=batch)
    rows, predictions = [], []
    for index, record in enumerate(records):
        with Image.open(resolve_image(Path(manifest["dataset_root"]), record["file"])) as photo:
            image = photo.convert("RGB")
        started = time.perf_counter()
        result = pipeline.predict(image, tiled=tiled)
        rows.append(
            {
                "image_id": record["id"],
                "ms": (time.perf_counter() - started) * 1000,
                **result["timings"],
            }
        )
        predictions.append({"image_id": record["id"], **result["prediction"]})
        if index % 50 == 0:
            print(f"Runtime {models.name} batch {batch}: {index + 1}/{len(records)}", flush=True)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    save_json(
        output,
        {
            "model": str(models),
            "batch_size": batch,
            "tiled": tiled,
            "split": "valid",
            "dataset_fingerprint": manifest["fingerprint"],
            "load_ms": pipeline.load_ms,
            "platform": platform.platform(),
            "torch_imported": "torch" in sys.modules,
            "peak_rss_mib": rss / (1024**2 if sys.platform == "darwin" else 1024),
            "median_ms": statistics.median(row["ms"] for row in rows),
            "p95_ms": float(np.percentile([r["ms"] for r in rows], 95)),
            "samples": rows,
            "predictions": predictions,
        },
    )


def benchmark(models, manifest_path, output, limit, batches, tiled=False):
    if output.exists():
        raise ValueError("Use a fresh benchmark directory.")
    output.mkdir(parents=True)
    manifest = read_manifest(manifest_path)
    summaries = []
    for model in models:
        for batch in batches:
            path = output / f"{model.name}-b{batch}.json"
            command = [
                sys.executable,
                "-m",
                "scanner.ml.runtime_experiment",
                "worker",
                "--models",
                str(model),
                "--manifest",
                str(manifest_path),
                "--output",
                str(path),
                "--limit",
                str(limit),
                "--batch",
                str(batch),
            ]
            if tiled:
                command.append("--tiled")
            subprocess.run(command, check=True)
            result = json.loads(path.read_text())
            from .benchmark import piece_diagnostics

            ids = {p["image_id"] for p in result["predictions"]}
            records = [r for r in manifest["records"] if r["id"] in ids]
            metrics = piece_diagnostics(result["predictions"], records, 0.0)
            summary = {k: v for k, v in result.items() if k not in {"samples", "predictions"}}
            summary["metrics"] = {
                k: metrics[k]
                for k in (
                    "typed_piece_recall",
                    "typed_prediction_precision",
                    "conditional_type_color_accuracy",
                    "missed_pieces",
                    "unmatched_predictions",
                    "annotated_pieces",
                )
            }
            summaries.append(summary)
            save_json(output / "summary.json", summaries)
            print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["quantize", "benchmark", "worker"])
    parser.add_argument("--models", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json"),
    )
    parser.add_argument(
        "--cache", type=Path, default=Path("scanner/artifacts/crops/chess-v2-v3-160")
    )
    parser.add_argument(
        "--limit", type=int, default=30, help="0 evaluates the full validation split"
    )
    parser.add_argument("--batch", type=int, nargs="+", default=[1])
    parser.add_argument("--tiled", action="store_true")
    args = parser.parse_args()
    if args.action == "quantize":
        quantize(args.models[0], args.output, args.cache)
    elif args.action == "worker":
        worker(args.models[0], args.manifest, args.output, args.limit, args.batch[0], args.tiled)
    else:
        benchmark(args.models, args.manifest, args.output, args.limit, args.batch, args.tiled)
