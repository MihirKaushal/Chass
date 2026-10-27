"""Small second-stage classifier; labels stay independent of the detector's guess."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms
from torchvision.models import ResNet18_Weights, resnet18

from .crops import prepare_crops
from .data import CLASSES, save_json
from .model import choose_device

ARCHITECTURE = "resnet18_piece_crops_v1"
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


def crop_transform(training=False):
    operations = []
    if training:
        operations += [
            transforms.RandomHorizontalFlip(),
            transforms.RandomAffine(12, translate=(0.05, 0.05), scale=(0.9, 1.1), fill=127),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
        ]
    return transforms.Compose([*operations, transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


class PieceCrops(Dataset):
    def __init__(self, root, index, split):
        self.root = root
        self.records = [record for record in index["records"] if record["split"] == split]
        self.transform = crop_transform(split == "train")

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        with Image.open(self.root / record["crop"]) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, record["label"] - 1


def build_classifier(pretrained=False):
    model = resnet18(weights=ResNet18_Weights.DEFAULT if pretrained else None)
    model.fc = nn.Linear(model.fc.in_features, len(CLASSES) - 1)
    return model


def load_classifier(path, device):
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != ARCHITECTURE or checkpoint.get("classes") != list(
        CLASSES[1:]
    ):
        raise ValueError("Unsupported piece classifier checkpoint.")
    model = build_classifier()
    model.load_state_dict(checkpoint["model"])
    return model.to(device).eval(), checkpoint


def classification_metrics(confusion):
    matrix = np.asarray(confusion, dtype=np.int64)
    support, predicted = matrix.sum(axis=1), matrix.sum(axis=0)
    correct = matrix.diagonal()
    recalls = np.divide(correct, support, out=np.zeros(12), where=support > 0)
    f1 = np.divide(
        2 * correct, support + predicted, out=np.zeros(12), where=(support + predicted) > 0
    )
    active = support > 0
    total = int(matrix.sum())
    return {
        "samples": total,
        "accuracy": float(correct.sum() / total) if total else None,
        "balanced_accuracy": float(recalls[active].mean()) if active.any() else None,
        "macro_f1": float(f1[active].mean()) if active.any() else None,
        "per_class": [
            {
                "class": name,
                "support": int(support[i]),
                "recall": float(recalls[i]),
                "f1": float(f1[i]),
            }
            for i, name in enumerate(CLASSES[1:])
        ],
        "confusion": matrix.tolist(),
    }


@torch.inference_mode()
def evaluate_classifier(model, loader, device):
    model.eval()
    confusion = np.zeros((12, 12), dtype=np.int64)
    for images, labels in loader:
        predictions = model(images.to(device)).argmax(1).cpu().numpy()
        np.add.at(confusion, (labels.numpy(), predictions), 1)
    return classification_metrics(confusion)


def atomic_checkpoint(path, payload):
    temporary = path.with_suffix(".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def train(manifest_path, cache, output, config):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new output directory; trained runs are immutable.")
    output.mkdir(parents=True, exist_ok=True)
    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(config["threads"])
    device = choose_device(config["device"])
    index = prepare_crops(manifest_path, cache, size=config["size"], context=config["context"])
    training, validation = PieceCrops(cache, index, "train"), PieceCrops(cache, index, "valid")
    counts = Counter(record["label"] for record in training.records)
    if set(counts) != set(range(1, 13)):
        raise ValueError("All twelve piece classes must appear in training.")
    sampler = WeightedRandomSampler(
        [1 / counts[r["label"]] for r in training.records],
        config["samples_per_epoch"],
        replacement=True,
        generator=torch.Generator().manual_seed(seed),
    )
    loader_options = {
        "batch_size": config["batch_size"],
        "num_workers": config["workers"],
        "persistent_workers": config["workers"] > 0,
    }
    train_loader = DataLoader(training, sampler=sampler, **loader_options)
    valid_loader = DataLoader(validation, shuffle=False, **loader_options)
    model = build_classifier(pretrained=True).to(device)
    # Keep the early visual features fixed; train the last two residual stages and head.
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name.startswith(("layer3.", "layer4.", "fc.")))
    optimizer = torch.optim.AdamW(
        [
            {
                "params": [
                    p
                    for name, p in model.named_parameters()
                    if p.requires_grad and not name.startswith("fc.")
                ],
                "lr": config["backbone_lr"],
            },
            {"params": model.fc.parameters(), "lr": config["head_lr"]},
        ],
        weight_decay=0.0001,
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    best, history, started, stale = -1, [], time.perf_counter(), 0
    save_json(
        output / "config.json",
        {
            **config,
            "dataset_fingerprint": index["dataset_fingerprint"],
            "crop_fingerprint": index["fingerprint"],
        },
    )
    for epoch in range(1, config["epochs"] + 1):
        epoch_start, loss_sum, count = time.perf_counter(), 0, 0
        model.train()
        # Frozen feature batch statistics must not drift on the balanced resampling stream.
        for block in (model.bn1, model.layer1, model.layer2):
            block.eval()
        for images, labels in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images.to(device)), labels.to(device))
            if not torch.isfinite(loss):
                raise RuntimeError("Classifier training produced a non-finite loss.")
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * len(labels)
            count += len(labels)
        metrics = evaluate_classifier(model, valid_loader, device)
        row = {
            "epoch": epoch,
            "loss": loss_sum / count,
            "validation": metrics,
            "seconds": time.perf_counter() - epoch_start,
        }
        history.append(row)
        payload = {
            "architecture": ARCHITECTURE,
            "classes": list(CLASSES[1:]),
            "config": config,
            "dataset_fingerprint": index["dataset_fingerprint"],
            "epoch": epoch,
            "model": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "validation": metrics,
        }
        atomic_checkpoint(output / "last.pt", payload)
        if metrics["macro_f1"] > best:
            best, stale = metrics["macro_f1"], 0
            atomic_checkpoint(output / "best.pt", payload)
        else:
            stale += 1
        save_json(output / "history.json", history)
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "loss": row["loss"],
                    "valid_accuracy": metrics["accuracy"],
                    "valid_macro_f1": metrics["macro_f1"],
                    "seconds": row["seconds"],
                }
            ),
            flush=True,
        )
        if stale >= config["patience"]:
            break
    result = {
        "training_seconds": time.perf_counter() - started,
        "best_validation_macro_f1": best,
        "checkpoint_sha256": hashlib.sha256((output / "best.pt").read_bytes()).hexdigest(),
        "device": str(device),
        "epochs": len(history),
    }
    save_json(output / "training.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).parent / "configs/crop-classifier.json"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            train(args.manifest, args.cache, args.output, json.loads(args.config.read_text())),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
