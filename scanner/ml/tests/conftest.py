import json

import pytest
import torch
from PIL import Image

from scanner.ml.data import SPLITS


@pytest.fixture(autouse=True, scope="session")
def limit_threads():
    torch.set_num_threads(2)


@pytest.fixture
def dataset_root(tmp_path):
    root = tmp_path / "data"
    for index, split in enumerate(SPLITS):
        folder = root / split
        folder.mkdir(parents=True)
        filename = f"board-{split}.rf.hash.jpg"
        Image.new("RGB", (64, 48), (20 + index * 50, 40, 60)).save(folder / filename)
        coco = {
            "categories": [{"id": 0, "name": "chess-pieces"}, {"id": 41, "name": "white-rook"}],
            "images": [{"id": 3, "file_name": filename, "width": 64, "height": 48}],
            "annotations": [
                {"id": 8, "image_id": 3, "category_id": 41, "bbox": [5, 6, 10, 12], "iscrowd": 0}
            ],
        }
        (folder / "_annotations.coco.json").write_text(json.dumps(coco))
    return root


def change_annotations(root, change, split="train"):
    path = root / split / "_annotations.coco.json"
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))
