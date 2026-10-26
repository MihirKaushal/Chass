import subprocess
import sys

import pytest
import torch
from PIL import Image

from scanner.ml.data import CLASSES, detector_tensor
from scanner.ml.model import ARCHITECTURE, build_model, load_checkpoint
from scanner.ml.train import save_checkpoint


def test_checkpoint_roundtrip_needs_no_download_and_predicts(tmp_path):
    model = build_model().eval()
    assert model.head.classification_head.num_columns == len(CLASSES)
    path = tmp_path / "model.pt"
    save_checkpoint(
        path, {"architecture": ARCHITECTURE, "classes": list(CLASSES), "model": model.state_dict()}
    )
    restored, _ = load_checkpoint(path, torch.device("cpu"))
    with torch.inference_mode():
        result = restored([torch.zeros(3, 64, 64)])[0]
    assert set(result) == {"boxes", "scores", "labels"}
    assert result["boxes"].shape[1] == 4
    assert torch.all(result["labels"] < len(CLASSES))
    assert not path.with_suffix(".tmp").exists()


def test_wrong_checkpoint_mapping_is_rejected(tmp_path):
    path = tmp_path / "bad.pt"
    torch.save({"architecture": ARCHITECTURE, "classes": ["wrong"]}, path)
    with pytest.raises(ValueError, match="class mapping"):
        load_checkpoint(path, torch.device("cpu"))


def test_cli_does_not_tune_test_threshold():
    result = subprocess.run(
        [sys.executable, "-m", "scanner.ml", "evaluate", "--split", "test"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "chosen using validation" in result.stderr


def test_cpu_presizing_matches_native_detector_transform():
    image = Image.frombytes("RGB", (96, 72), bytes(range(256)) * 81)
    model = build_model().eval()
    native, _ = model.transform([detector_tensor(image)])
    presized, _ = model.transform([detector_tensor(image, 320)])
    torch.testing.assert_close(presized.tensors, native.tensors, atol=1e-6, rtol=1e-4)
