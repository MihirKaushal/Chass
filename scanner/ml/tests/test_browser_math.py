"""Check JS preprocessing against Pillow/NumPy without a browser or model download."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from scanner.ml.crops import piece_crop
from scanner.ml.onnx_inference import resize_bilinear

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(not shutil.which("node"), reason="Node is required for JS parity")
@pytest.mark.parametrize(
    "shape,box",
    [
        ((40, 60), [5, 2, 50, 37]),
        ((80, 45), [1, 3, 30, 75]),
        ((160, 160), [0, 0, 160, 160]),
        ((240, 200), [12.5, 28.2, 180.7, 220.9]),
    ],
)
def test_browser_preprocessing_matches_python(shape, box):
    pixels = np.random.default_rng(42).integers(0, 256, (*shape, 3), dtype=np.uint8)
    image = Image.fromarray(pixels)
    rgba = np.asarray(image.convert("RGBA"))
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            """
import { cropPixels, detectorTensor } from './frontend/src/scanner/browserMath.js';
let text = ''; for await (const chunk of process.stdin) text += chunk;
const {image, box} = JSON.parse(text);
console.log(JSON.stringify({crop: [...cropPixels(image, box, {size: 160, context: .15})],
  detector: [...detectorTensor(image, 32)]}));
""",
        ],
        input=json.dumps(
            {
                "image": {
                    "data": rgba.flatten().tolist(),
                    "width": image.width,
                    "height": image.height,
                },
                "box": box,
            }
        ),
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    actual = json.loads(result.stdout)
    np.testing.assert_array_equal(actual["crop"], np.asarray(piece_crop(image, box)).flatten())
    np.testing.assert_allclose(actual["detector"], resize_bilinear(image, 32).flatten(), atol=1e-5)
