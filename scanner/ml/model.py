from __future__ import annotations

from functools import partial
from pathlib import Path

import torch
from torch import nn
from torchvision.models.detection import (
    SSDLite320_MobileNet_V3_Large_Weights,
    ssdlite320_mobilenet_v3_large,
)
from torchvision.models.detection.ssdlite import SSDLiteClassificationHead

from .data import CLASSES

ARCHITECTURE = "ssdlite320_mobilenet_v3_large"


def build_model(*, pretrained: bool = False):
    if pretrained:
        model = ssdlite320_mobilenet_v3_large(
            weights=SSDLite320_MobileNet_V3_Large_Weights.DEFAULT,
        )
        channels = [block[0][0].in_channels for block in model.head.classification_head.module_list]
        model.head.classification_head = SSDLiteClassificationHead(
            channels,
            model.anchor_generator.num_anchors_per_location(),
            len(CLASSES),
            partial(nn.BatchNorm2d, eps=0.001, momentum=0.03),
        )
    else:
        model = ssdlite320_mobilenet_v3_large(
            weights=None,
            weights_backbone=None,
            num_classes=len(CLASSES),
        )
    # Keep low-score candidates for COCO evaluation; the operating threshold is chosen on validation.
    model.score_thresh = 0.01
    model.detections_per_img = 100
    return model


def choose_device(requested: str = "auto") -> torch.device:
    if requested == "auto":
        requested = (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
    if requested == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS is unavailable; choose --device cpu.")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable; choose --device cpu.")
    return torch.device(requested)


def load_checkpoint(path: Path, device: torch.device):
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint.get("architecture") != ARCHITECTURE or checkpoint.get("classes") != list(CLASSES):
        raise ValueError("The checkpoint architecture/class mapping does not match this scanner.")
    model = build_model()
    model.load_state_dict(checkpoint["model"])
    return model.to(device).eval(), checkpoint
