import numpy as np
import pytest
import torch
from PIL import Image
from torchvision.ops import nms as torch_nms

pytest.importorskip("onnxruntime")

from scanner.ml.data import detector_tensor
from scanner.ml.onnx_inference import nms, resize_bilinear, softmax


@pytest.mark.parametrize("size", [(320, 320), (416, 416), (800, 600), (128, 160)])
def test_resize_matches_torch_half_pixel_sampling(size):
    pixels = np.random.default_rng(1).integers(0, 256, (*size, 3), dtype=np.uint8)
    image = Image.fromarray(pixels)
    expected = detector_tensor(image, 320).numpy()[None]
    np.testing.assert_allclose(resize_bilinear(image, 320), expected, rtol=0, atol=0.0001)


def test_nms_matches_torch():
    boxes = np.asarray([[1, 1, 20, 20], [2, 2, 21, 21], [40, 40, 50, 50]], dtype=np.float32)
    scores = np.asarray([0.9, 0.8, 0.7], dtype=np.float32)
    assert (
        nms(boxes, scores, 0.45)
        == torch_nms(torch.from_numpy(boxes), torch.from_numpy(scores), 0.45).tolist()
    )


@pytest.mark.parametrize(
    "logits",
    [
        [[1000, -1000, 1001]],
        [[0] * 13, [1000] * 13],
        [[-1000, -1001, -1002]],
        np.random.default_rng(7).normal(0, 10, (32, 13)),
    ],
    ids=["extreme", "equal", "negative", "varied"],
)
def test_softmax_probabilities_match_torch(logits):
    logits = np.asarray(logits, dtype=np.float32)
    actual = softmax(logits)
    expected = torch.from_numpy(logits).softmax(-1).numpy()
    # Float32 exp/reduction kernels round differently across CPU platforms.
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-8)
    assert actual.dtype == np.float32
    assert np.isfinite(actual).all()
    assert ((actual >= 0) & (actual <= 1)).all()
    np.testing.assert_allclose(actual.sum(axis=-1), 1, rtol=0, atol=4 * np.finfo(np.float32).eps)
    np.testing.assert_array_equal(actual.argmax(axis=-1), expected.argmax(axis=-1))
