import copy

import numpy as np
import pytest
from PIL import Image

from scanner.ml.classifier import classification_metrics
from scanner.ml.crops import piece_crop
from scanner.ml.geometry import assign_squares, square_metrics
from scanner.ml.label_review import apply_review
from scanner.ml.postprocess import resolve_duplicates
from scanner.ml.square_benchmark import evaluate as evaluate_squares


def prediction():
    return {
        "image_id": 1,
        "boxes": [[10, 10, 80, 80], [11, 11, 81, 81], [110, 10, 180, 80]],
        "labels": [2, 5, 4],
        "scores": [0.9, 0.8, 0.7],
    }


def test_duplicate_suppression_crosses_labels_but_preserves_neighbors():
    original = prediction()
    result = resolve_duplicates(original)
    assert result["labels"] == [2, 4]
    assert result["duplicate_counts"] == [1, 0]
    assert len(original["boxes"]) == 3


def test_suppression_ties_are_deterministic_and_threshold_inclusive():
    item = prediction()
    item["scores"] = [0.25, 0.25, 0.24]
    assert resolve_duplicates(item)["labels"] == [2]


@pytest.mark.parametrize("threshold,overlap", [(float("nan"), 0.5), (0.2, 0), (2, 0.5)])
def test_suppression_rejects_invalid_thresholds(threshold, overlap):
    with pytest.raises(ValueError):
        resolve_duplicates(prediction(), threshold=threshold, overlap=overlap)


def test_crop_preserves_aspect_and_handles_edges():
    image = Image.new("RGB", (100, 100), "white")
    crop = piece_crop(image, [0, 0, 20, 80], context=0.15, size=160)
    assert crop.size == (160, 160)
    assert crop.getpixel((0, 0)) == (127, 127, 127)
    assert crop.getpixel((80, 80)) == (255, 255, 255)


@pytest.mark.parametrize("box", [[1, 1, 1, 5], [float("nan"), 1, 5, 5], [200, 200, 220, 240]])
def test_crop_rejects_degenerate_boxes(box):
    with pytest.raises(ValueError):
        piece_crop(Image.new("RGB", (100, 100)), box)


def test_balanced_metrics_do_not_hide_rare_class_errors():
    confusion = np.zeros((12, 12), dtype=int)
    confusion[0, 0], confusion[1, 0] = 99, 1
    metrics = classification_metrics(confusion)
    assert metrics["accuracy"] == 0.99
    assert metrics["balanced_accuracy"] == 0.5


def test_square_assignment_orientation_and_collision_review():
    result = assign_squares(prediction(), 800, 800)
    assert result["board"][0][:2] == ["black-king", "black-pawn"]
    assert result["reviewSquares"][0]["label"] == "a8"
    assert any("Multiple" in reason for reason in result["reviewSquares"][0]["reasons"])
    assert len(result["squareCandidates"][0]["candidates"]) == 2


def test_square_assignment_flags_boundaries():
    item = {"boxes": [[85, 20, 105, 80]], "labels": [12], "scores": [0.9]}
    result = assign_squares(item, 800, 800)
    assert "boundary" in result["reviewSquares"][0]["reasons"][0]


def test_real_square_metrics_penalize_missing_invented_and_wrong_pieces():
    actual = [[None] * 8 for _ in range(8)]
    actual[0][0], actual[0][1] = "black-king", "white-rook"
    predicted = copy.deepcopy(actual)
    predicted[0][0], predicted[0][1], predicted[0][2] = None, "white-bishop", "white-pawn"
    metrics = square_metrics([predicted], [actual])
    assert metrics["occupancy_accuracy"] == 62 / 64
    assert metrics["overall_13_class_square_accuracy"] == 61 / 64
    assert metrics["occupied_square_type_color_accuracy"] == 0
    assert metrics["exact_board_accuracy"] == 0
    assert metrics["missed"] == metrics["invented"] == 1


def test_empty_actual_board_does_not_invent_piece_accuracy():
    board = [[None] * 8 for _ in range(8)]
    assert square_metrics([board], [board])["occupied_square_type_color_accuracy"] is None
    with pytest.raises(ValueError):
        square_metrics([], [])


def test_review_changes_fingerprint_without_mutating_source():
    manifest = {
        "fingerprint": "original",
        "records": [
            {
                "id": 1,
                "sha256": "photo",
                "width": 100,
                "height": 100,
                "boxes": [],
                "labels": [],
                "iscrowd": [],
                "split": "test",
            }
        ],
    }
    review = {
        "source_fingerprint": "original",
        "additions": [
            {
                "image_id": 1,
                "image_sha256": "photo",
                "box": [1, 2, 8, 9],
                "label": "black-pawn",
                "reason": "Reviewed",
            }
        ],
    }
    result = apply_review(manifest, review)
    assert result["fingerprint"] != manifest["fingerprint"]
    assert result["records"][0]["labels"] == [4]
    assert manifest["records"][0]["labels"] == []
    with pytest.raises(ValueError, match="fingerprint"):
        apply_review(result, review)
    review["source_fingerprint"] = result["fingerprint"]
    with pytest.raises(ValueError, match="overlaps"):
        apply_review(result, review)


def test_square_benchmark_rejects_unverified_or_mismatched_photo_labels():
    record = {
        "image_id": "sample",
        "image_sha256": "hash",
        "verified": True,
        "orientation": "white_bottom",
        "board": [[None] * 8 for _ in range(8)],
    }
    truth = {"records": [record]}
    predicted = copy.deepcopy(truth)
    assert evaluate_squares(predicted, truth)["exact_board_accuracy"] == 1
    predicted["records"][0]["image_sha256"] = "different"
    with pytest.raises(ValueError, match="hashes"):
        evaluate_squares(predicted, truth)
    predicted = copy.deepcopy(truth)
    record["verified"] = False
    with pytest.raises(ValueError, match="verified"):
        evaluate_squares(predicted, truth)
