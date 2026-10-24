import json
from pathlib import Path

import pytest

from scanner.ml.train import train


@pytest.mark.parametrize(
    "key,value",
    [
        ("batch_size", 1),
        ("learning_rate", 0),
        ("backbone_learning_rate", float("nan")),
        ("epochs", 0),
        ("threads", 0),
        ("weight_decay", -1),
        ("patience", 0),
    ],
)
def test_invalid_training_configuration_is_rejected_before_model_download(tmp_path, key, value):
    config = json.loads((Path(__file__).parents[1] / "configs/baseline.json").read_text())
    config[key] = value
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="positive"):
        train(tmp_path / "absent-manifest", config_path, tmp_path / "run")


def test_new_run_does_not_overwrite_previous_weights(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    (output / "best.pt").write_bytes(b"previous weights")
    with pytest.raises(ValueError, match="already has checkpoints"):
        train(
            tmp_path / "absent-manifest",
            Path(__file__).parents[1] / "configs/baseline.json",
            output,
        )
    assert (output / "best.pt").read_bytes() == b"previous weights"
