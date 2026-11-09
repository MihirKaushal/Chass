import pytest
import torch

from scanner.ml.data import CocoPieces, prepare_dataset, read_manifest
from scanner.ml.metrics import box_iou, coco_metrics, collect_predictions, operating_metrics


@pytest.fixture
def record():
    return {
        "id": 1,
        "width": 64,
        "height": 48,
        "boxes": [[5, 6, 15, 18]],
        "labels": [12],
        "iscrowd": [0],
    }


def prediction(boxes=None, labels=None, scores=None):
    return {
        "image_id": 1,
        "boxes": boxes if boxes is not None else [[5, 6, 15, 18]],
        "labels": labels if labels is not None else [12],
        "scores": scores if scores is not None else [0.9],
    }


def test_perfect_detection(record):
    result = operating_metrics([prediction()], [record], 0.5)
    assert result["tp"] == 1 and result["fp"] == result["fn"] == 0
    assert result["f1"] == result["exact_detection_image_rate"] == 1
    coco = coco_metrics([prediction()], [record])
    assert coco["map50"] == pytest.approx(1)
    assert coco["map50_95"] == pytest.approx(1)
    assert coco["per_class_ap50"]["black-king"] is None


def test_wrong_class_is_false_positive_and_missed_piece(record):
    result = operating_metrics([prediction(labels=[1])], [record], 0.5)
    assert result["tp"] == 0 and result["fp"] == result["fn"] == 1
    assert coco_metrics([prediction(labels=[1])], [record])["map50"] == 0


def test_duplicate_and_threshold(record):
    duplicate = prediction(boxes=record["boxes"] * 2, labels=[12, 12], scores=[0.9, 0.6])
    result = operating_metrics([duplicate], [record], 0.5)
    assert result["tp"] == result["fp"] == 1
    assert result["exact_detection_images"] == 0
    assert operating_metrics([duplicate], [record], 0.7)["f1"] == 1
    missed = operating_metrics([duplicate], [record], 0.95)
    assert missed["fn"] == 1 and missed["tp"] == missed["fp"] == 0


def test_empty_predictions(record):
    empty = prediction(boxes=[], labels=[], scores=[])
    assert operating_metrics([empty], [record], 0.5)["recall"] == 0
    assert coco_metrics([empty], [record])["map50"] == 0


def test_localization_must_overlap(record):
    result = operating_metrics([prediction(boxes=[[40, 30, 50, 40]])], [record], 0.5)
    assert result["fp"] == result["fn"] == 1
    assert box_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1
    assert box_iou([0, 0, 1, 1], [2, 2, 3, 3]) == 0


def test_collect_predictions_restores_original_photo_coordinates(dataset_root, tmp_path):
    prepare_dataset(dataset_root, tmp_path / "prepared")
    dataset = CocoPieces(
        read_manifest(tmp_path / "prepared/manifest.json"), "valid", input_size=320
    )

    class Detector(torch.nn.Module):
        def forward(self, images):
            return [
                {
                    "boxes": torch.tensor([[25.0, 40.0, 75.0, 120.0]]),
                    "labels": torch.tensor([12]),
                    "scores": torch.tensor([0.9]),
                }
                for _ in images
            ]

    predictions, _ = collect_predictions(Detector(), dataset, torch.device("cpu"))
    assert predictions[0]["boxes"] == [[5.0, 6.0, 15.0, 18.0]]
    assert operating_metrics(predictions, dataset.records, 0.5)["f1"] == 1.0
