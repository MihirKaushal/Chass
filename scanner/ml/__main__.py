from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

# Torch must see this before importing the MPS backend. Unsupported operations can use CPU.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from .data import (
    DEFAULT_ARTIFACTS,
    CocoPieces,
    prepare_dataset,
    read_manifest,
    save_json,
)
from .datasets import DATASETS, prepared_directory


def main():
    parser = argparse.ArgumentParser(
        description="Offline Chass scanner: audit, train, evaluate, and predict."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser(
        "prepare", help="Audit COCO data and preserve its existing grouped splits."
    )
    prepare.add_argument("--dataset", choices=sorted(DATASETS), default="top-down")
    prepare.add_argument(
        "--data", type=Path, help="Override the selected profile's image directory."
    )
    prepare.add_argument(
        "--output", type=Path, help="Override the selected profile's prepared directory."
    )
    curation = commands.add_parser(
        "curate", help="Build a separate, reviewed and leakage-safe COCO version."
    )
    curation.add_argument("--dataset", choices=sorted(DATASETS), default="chess-v2")
    curation.add_argument("--data", type=Path)
    curation.add_argument(
        "--policy", type=Path, default=Path(__file__).parent / "configs/chess-v2-clean-v2.json"
    )
    curation.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/curated/chess-v2-v2",
    )
    curation.add_argument("--report", type=Path, default=DEFAULT_ARTIFACTS / "curation/chess-v2-v2")
    comparison = commands.add_parser(
        "compare", help="Check two audited datasets for possible overlap without merging."
    )
    comparison.add_argument(
        "--first", type=Path, default=DEFAULT_ARTIFACTS / "prepared/manifest.json"
    )
    comparison.add_argument(
        "--second",
        type=Path,
        default=DEFAULT_ARTIFACTS / "curation/chess-v2-v2/prepared/manifest.json",
    )
    comparison.add_argument(
        "--output", type=Path, default=DEFAULT_ARTIFACTS / "curation/chess-v2-v2/cross-source.json"
    )
    training = commands.add_parser("train")
    training.add_argument(
        "--manifest", type=Path, default=DEFAULT_ARTIFACTS / "prepared/manifest.json"
    )
    training.add_argument(
        "--config", type=Path, default=Path(__file__).parent / "configs/baseline.json"
    )
    training.add_argument("--output", type=Path, default=DEFAULT_ARTIFACTS / "baseline")
    training.add_argument("--resume", type=Path)
    training.add_argument("--epochs", type=int)
    training.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument(
        "--manifest", type=Path, default=DEFAULT_ARTIFACTS / "prepared/manifest.json"
    )
    evaluate.add_argument("--checkpoint", type=Path, default=DEFAULT_ARTIFACTS / "baseline/best.pt")
    evaluate.add_argument("--split", choices=["valid", "test"], default="valid")
    evaluate.add_argument(
        "--threshold", type=float, help="Required for test; choose it on validation first."
    )
    evaluate.add_argument("--output", type=Path, default=DEFAULT_ARTIFACTS / "evaluation")
    evaluate.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    prediction = commands.add_parser("predict")
    prediction.add_argument("image", type=Path)
    prediction.add_argument(
        "--checkpoint", type=Path, default=DEFAULT_ARTIFACTS / "baseline/best.pt"
    )
    prediction.add_argument("--threshold", type=float, default=0.3)
    prediction.add_argument("--output", type=Path, default=DEFAULT_ARTIFACTS / "prediction")
    prediction.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    args = parser.parse_args()
    if args.command == "prepare":
        profile = DATASETS[args.dataset]
        try:
            result = prepare_dataset(
                args.data or profile.root,
                args.output or prepared_directory(profile),
                profile=profile,
            )
        except ValueError as error:
            parser.exit(2, f"{error}\n")
    elif args.command == "curate":
        from .curation import curate

        profile = DATASETS[args.dataset]
        if args.data:
            profile = replace(profile, root=args.data)
        try:
            result = curate(profile, args.policy, args.output, args.report)
        except ValueError as error:
            parser.exit(2, f"{error}\n")
    elif args.command == "compare":
        from .compare import compare_manifests

        result = compare_manifests(args.first, args.second, args.output)
    elif args.command == "train":
        from .train import train

        result = train(
            args.manifest,
            args.config,
            args.output,
            device_name=args.device,
            resume=args.resume,
            epoch_override=args.epochs,
        )
    elif args.command == "evaluate":
        if args.split == "test" and args.threshold is None:
            parser.error(
                "Test evaluation requires --threshold chosen using validation, not the test set."
            )
        if args.threshold is not None and not 0 <= args.threshold <= 1:
            parser.error("--threshold must be between 0 and 1.")
        import torch

        from .metrics import coco_metrics, collect_predictions, operating_metrics
        from .model import choose_device, load_checkpoint
        from .report import evaluation_report

        manifest = read_manifest(args.manifest)
        device = choose_device(args.device)
        model, checkpoint = load_checkpoint(args.checkpoint, device)
        torch.set_num_threads(checkpoint["config"].get("threads", 4))
        if checkpoint["dataset_fingerprint"] != manifest["fingerprint"]:
            parser.error(
                "Checkpoint/dataset fingerprints differ; evaluate on the original manifest."
            )
        dataset = CocoPieces(
            manifest, args.split, input_size=checkpoint["config"].get("input_size")
        )
        predictions, timing = collect_predictions(model, dataset, device)
        threshold = args.threshold
        if threshold is None:
            sweep = [
                operating_metrics(predictions, dataset.records, step / 20) for step in range(2, 19)
            ]
            threshold = max(sweep, key=lambda value: (value["f1"], value["threshold"]))["threshold"]
            save_json(
                args.output / "threshold_sweep.json",
                [
                    {key: value[key] for key in ("threshold", "precision", "recall", "f1")}
                    for value in sweep
                ],
            )
        result = {
            **coco_metrics(predictions, dataset.records),
            **operating_metrics(predictions, dataset.records, threshold),
            "split": args.split,
            "checkpoint_epoch": checkpoint["epoch"],
            "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
            "dataset_fingerprint": manifest["fingerprint"],
            "timing": timing,
        }
        save_json(args.output / "metrics.json", result)
        save_json(args.output / "predictions.json", predictions)
        evaluation_report(
            args.output / "report", dataset.root, dataset.records, predictions, result
        )
    else:
        if not 0 <= args.threshold <= 1:
            parser.error("--threshold must be between 0 and 1.")
        import torch
        from PIL import Image, ImageOps

        from .data import CLASSES, detector_tensor, resize_boxes
        from .model import choose_device, load_checkpoint
        from .report import draw_predictions

        device = choose_device(args.device)
        torch.set_num_threads(4)
        model, checkpoint = load_checkpoint(args.checkpoint, device)
        with Image.open(args.image) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
        tensor = detector_tensor(image, checkpoint["config"].get("input_size"))
        with torch.inference_mode():
            output = model([tensor.to(device)])[0]
            output["boxes"] = resize_boxes(
                output["boxes"], (tensor.shape[-1], tensor.shape[-2]), image.size
            )
            prediction = {key: value.cpu().tolist() for key, value in output.items()}
        pieces = [
            {"piece": CLASSES[label], "confidence": score, "box_xyxy": box}
            for box, label, score in zip(
                prediction["boxes"], prediction["labels"], prediction["scores"], strict=True
            )
            if score >= args.threshold
        ]
        result = {
            "task": "piece_detection",
            "image": args.image.name,
            "width": image.width,
            "height": image.height,
            "coordinate_space": "EXIF-oriented image pixels",
            "threshold": args.threshold,
            "checkpoint_epoch": checkpoint["epoch"],
            "pieces": pieces,
            "warning": "These are piece boxes, not verified squares or a playable board position.",
        }
        save_json(args.output / "prediction.json", result)
        draw_predictions(
            image, prediction["boxes"], prediction["labels"], prediction["scores"], args.threshold
        ).save(args.output / "annotated.jpg", quality=95)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
