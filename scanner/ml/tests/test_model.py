import subprocess
import sys

import pytest
import torch

from scanner.ml.data import CLASSES
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
