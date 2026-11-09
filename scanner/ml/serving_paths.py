"""Local Torch artifacts corresponding to the current public ONNX release."""

import os
from pathlib import Path

from .data import DEFAULT_ARTIFACTS


def model_paths():
    defaults = {
        "SCANNER_SELECTION": "merge-evaluation-2026-11-08/merged/selection.json",
        "SCANNER_DETECTOR": "merge-experiment-2026-11-08/merged/detector/best.pt",
        "SCANNER_CLASSIFIER": "merge-experiment-2026-11-08/merged/classifier/best.pt",
    }
    return tuple(Path(os.environ.get(key, DEFAULT_ARTIFACTS / value)) for key, value in defaults.items())
