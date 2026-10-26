from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .data import CLASSES, CocoPieces, collate_detection, read_manifest, save_json
from .metrics import coco_metrics, collect_predictions
from .model import ARCHITECTURE, build_model, choose_device


def save_checkpoint(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def train(
    manifest_path: Path,
    config_path: Path,
    output: Path,
    *,
    device_name="auto",
    resume: Path | None = None,
    epoch_override: int | None = None,
):
    config = json.loads(config_path.read_text())
    if epoch_override is not None:
        config["epochs"] = epoch_override
    if (
        config["epochs"] < 1
        or config["batch_size"] < 2
        or any(
            not math.isfinite(config[key]) or config[key] <= 0
            for key in ("learning_rate", "backbone_learning_rate")
        )
        or config["threads"] < 1
        or config["num_workers"] < 0
        or config["patience"] < 1
        or config["warmup_epochs"] < 0
        or not math.isfinite(config["weight_decay"])
        or config["weight_decay"] < 0
        or config.get("input_size") not in (None, 320)
    ):
        raise ValueError(
            "Use positive epochs, learning rates, threads and patience, batch size >= 2, "
            "and nonnegative warmup, workers and weight decay. Optional input_size must be 320."
        )
    if not resume and any((output / name).exists() for name in ("best.pt", "last.pt")):
        raise ValueError(
            "This run already has checkpoints; use --resume or a new --output directory."
        )
    manifest = read_manifest(manifest_path)
    device = choose_device(device_name)
    torch.set_num_threads(config["threads"])
    random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = torch.load(resume, map_location="cpu", weights_only=True) if resume else None
    if checkpoint and (
        checkpoint["dataset_fingerprint"] != manifest["fingerprint"]
        or checkpoint["classes"] != list(CLASSES)
        or checkpoint["architecture"] != ARCHITECTURE
    ):
        raise ValueError(
            "Resume checkpoint does not match this dataset, architecture, or class mapping."
        )
    if checkpoint:
        if resume.parent.resolve() != output.resolve() or not (output / "best.pt").exists():
            raise ValueError(
                "Resume in the original output directory, retaining its best.pt checkpoint."
            )
        if checkpoint["epoch"] >= config["epochs"]:
            raise ValueError("The epoch limit must exceed the resumed checkpoint epoch.")
        old = checkpoint["config"]
        if any(old[key] != config[key] for key in old if key != "epochs"):
            raise ValueError("Resume requires the original configuration; only epochs may change.")
    model = build_model(pretrained=checkpoint is None).to(device)
    if checkpoint:
        model.load_state_dict(checkpoint["model"])
    backbone = list(model.backbone.parameters())
    head = list(model.head.parameters())
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone, "lr": config["backbone_learning_rate"]},
            {"params": head, "lr": config["learning_rate"]},
        ],
        weight_decay=config["weight_decay"],
    )
    if checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer"])
        random.setstate(checkpoint["python_rng"])
        torch.set_rng_state(checkpoint["torch_rng"])
    train_data = CocoPieces(
        manifest, "train", augment=config["augment"], input_size=config.get("input_size")
    )
    valid_data = CocoPieces(manifest, "valid", input_size=config.get("input_size"))
    if len(train_data) < config["batch_size"] or not len(valid_data):
        raise ValueError("The training/validation sets are too small for this configuration.")
    # A one-image final batch cannot train SSDLite's 1x1 BatchNorm features.
    drop_last = len(train_data) % config["batch_size"] == 1
    generator = torch.Generator().manual_seed(config["seed"])
    if checkpoint and "loader_rng" in checkpoint:
        generator.set_state(checkpoint["loader_rng"])
    loader = DataLoader(
        train_data,
        batch_size=config["batch_size"],
        shuffle=True,
        num_workers=config["num_workers"],
        collate_fn=collate_detection,
        drop_last=drop_last,
        generator=generator,
    )
    save_json(output / "config.json", config)
    environment = {
        "torch": str(torch.__version__),
        "device": str(device),
        "seed": config["seed"],
        "dataset_fingerprint": manifest["fingerprint"],
        "task": "12-class piece detection",
    }
    save_json(output / "environment.json", environment)
    history = checkpoint.get("history", []) if checkpoint else []
    best = checkpoint.get("best_map50", -1.0) if checkpoint else -1.0
    stale = checkpoint.get("stale_epochs", 0) if checkpoint else 0
    start_epoch = checkpoint["epoch"] + 1 if checkpoint else 1
    if not checkpoint:
        predictions, timing = collect_predictions(model, valid_data, device, config["batch_size"])
        initial = {**coco_metrics(predictions, valid_data.records), "timing": timing}
        save_json(output / "untrained_head_validation.json", initial)
        print(
            json.dumps({"stage": "untrained_head", "validation_map50": initial["map50"]}),
            flush=True,
        )
    for epoch in range(start_epoch, config["epochs"] + 1):
        started = time.perf_counter()
        frozen = epoch <= config["warmup_epochs"]
        for parameter in backbone:
            parameter.requires_grad_(not frozen)
        model.train()
        if frozen:
            model.backbone.eval()
        totals, batches = {}, 0
        # Decay only after warmup; retain a nonzero fine-tuning rate on this small dataset.
        progress = max(0, epoch - config["warmup_epochs"] - 1) / max(
            1, config["epochs"] - config["warmup_epochs"]
        )
        factor = 0.1 + 0.9 * (1 + math.cos(math.pi * progress)) / 2
        optimizer.param_groups[0]["lr"] = config["backbone_learning_rate"] * factor
        optimizer.param_groups[1]["lr"] = config["learning_rate"] * factor
        for images, targets in loader:
            images = [image.to(device) for image in images]
            targets = [
                {key: value.to(device) for key, value in target.items()} for target in targets
            ]
            losses = model(images, targets)
            loss = sum(losses.values())
            if not torch.isfinite(loss):
                raise ValueError(f"Non-finite loss at epoch {epoch}: {losses}")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10)
            optimizer.step()
            for key, value in losses.items():
                totals[key] = totals.get(key, 0.0) + value.item()
            batches += 1
        predictions, timing = collect_predictions(model, valid_data, device, config["batch_size"])
        metrics = coco_metrics(predictions, valid_data.records)
        improved = metrics["map50"] > best
        if improved:
            best, stale = metrics["map50"], 0
        else:
            stale += 1
        row = {
            "epoch": epoch,
            "frozen_backbone": frozen,
            "losses": {key: value / batches for key, value in totals.items()},
            "validation_map50": metrics["map50"],
            "validation_map50_95": metrics["map50_95"],
            "seconds": time.perf_counter() - started,
        }
        history.append(row)
        payload = {
            "architecture": ARCHITECTURE,
            "classes": list(CLASSES),
            "epoch": epoch,
            "dataset_fingerprint": manifest["fingerprint"],
            "config": config,
            "model": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "optimizer": optimizer.state_dict(),
            "history": history,
            "best_map50": best,
            "stale_epochs": stale,
            "python_rng": random.getstate(),
            "torch_rng": torch.get_rng_state(),
            "loader_rng": generator.get_state(),
        }
        save_checkpoint(output / "last.pt", payload)
        if improved:
            save_checkpoint(output / "best.pt", payload)
            save_json(
                output / "best_validation.json", {**metrics, "epoch": epoch, "timing": timing}
            )
        save_json(output / "history.json", history)
        print(json.dumps(row), flush=True)
        if stale >= config["patience"]:
            print(
                json.dumps({"stage": "early_stop", "epoch": epoch, "best_validation_map50": best}),
                flush=True,
            )
            break
    return {
        "best_validation_map50": best,
        "epochs_completed": len(history),
        "checkpoint": str(output / "best.pt"),
    }
