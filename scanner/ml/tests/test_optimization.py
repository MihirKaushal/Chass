import numpy as np
import pytest
from PIL import Image, ImageOps

from scanner.ml.accuracy_experiment import passes
from scanner.ml.crops import piece_crop
from scanner.ml.onnx_inference import OnnxScannerPipeline


def test_candidate_must_pass_every_guard():
    baseline = {
        "typed_piece_recall": 0.85,
        "typed_prediction_precision": 0.95,
        "typed_f1": 0.90,
        "black_king_accuracy": 0.87,
        "white_king_accuracy": 0.95,
    }
    assert passes(baseline, baseline)
    for key in baseline:
        assert not passes({**baseline, key: baseline[key] - 0.01}, baseline)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
def test_cropping_before_conversion_matches_original_pixels(mode):
    pixels = np.random.default_rng(2).integers(0, 256, (500, 600, 3), dtype=np.uint8)
    photo = Image.fromarray(pixels).convert(mode)
    expected = ImageOps.pad(
        photo.convert("RGB").crop((17, 35, 43, 77)),
        (160, 160),
        method=Image.Resampling.BILINEAR,
        color=(127, 127, 127),
    )
    np.testing.assert_array_equal(piece_crop(photo, [20, 40, 40, 72]), expected)


def test_invalid_batch_rejected_before_loading_models():
    for batch in (0, 3, 8):
        with pytest.raises(ValueError, match="batch size"):
            OnnxScannerPipeline("missing", batch_size=batch)
