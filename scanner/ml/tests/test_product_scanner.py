import copy
import json

import numpy as np
import pytest

from scanner.ml.board_collection import collect
from scanner.ml.board_experiment import extra_review, remap
from scanner.ml.calibration import diagnostics, evaluate_validation, fit_temperature, probabilities
from scanner.ml.geometry import square_metrics
from scanner.ml.square_benchmark import evaluate
from scanner.ml.tests.test_board_collection import example


def test_square_diagnostics_include_misses_confusion_and_recall():
    truth = [[None] * 8 for _ in range(8)]
    truth[0][:3] = ["black-king", "white-rook", "white-pawn"]
    predicted = copy.deepcopy(truth)
    predicted[0][:4] = [None, "white-bishop", "white-pawn", "black-rook"]
    result = square_metrics([predicted], [truth])
    assert result["occupancy_recall"] == 2 / 3
    assert result["occupancy_precision"] == 2 / 3
    assert result["conditional_occupied_type_color_accuracy"] == 1 / 2
    assert result["mean_corrections_per_board"] == 3
    assert next(r for r in result["per_class"] if r["class"] == "black-king")["missed"] == 1
    assert next(r for r in result["per_class"] if r["class"] == "black-rook")["invented"] == 1


def test_review_metrics_measure_errors_caught_not_just_number_of_flags():
    board = [[None] * 8 for _ in range(8)]
    expected = {
        "image_id": "x",
        "image_sha256": "hash",
        "verified": True,
        "orientation": "white_bottom",
        "board": board,
    }
    found = copy.deepcopy(expected)
    found["board"][0][0] = "white-king"
    found["reviewSquares"] = [{"row": 0, "col": 0}, {"row": 0, "col": 1}]
    metrics = evaluate({"records": [found]}, {"records": [expected]})
    assert metrics["review"]["error_recall"] == 1
    assert metrics["review"]["flag_precision"] == 0.5
    assert metrics["per_board"][0]["incorrect_squares"] == ["a8"]
    del found["reviewSquares"]
    assert evaluate({"records": [found]}, {"records": [expected]})["review"]["measured"] is False


def test_direct_scoring_rejects_unaudited_user_exports():
    record = {
        "image_id": "x",
        "image_sha256": "hash",
        "verified": True,
        "orientation": "white_bottom",
        "board": [[None] * 8 for _ in range(8)],
        "verification": "user_reviewed_not_independently_audited",
    }
    with pytest.raises(ValueError, match="verified"):
        evaluate({"records": [record]}, {"records": [record]})


def test_user_exports_require_label_audit_and_source_groups_cannot_leak(tmp_path):
    export, digest, groups = example(tmp_path)
    data = json.loads(export.read_text())
    data["records"][0]["verification"] = "user_reviewed_not_independently_audited"
    export.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Recheck"):
        collect([export], tmp_path, groups)
    groups[digest]["labels_checked"] = True
    assert collect([export], tmp_path, groups)["records"][0]["verification"] == "collection_checked"
    other, other_hash, other_groups = example(tmp_path, "2")
    other_groups[other_hash].update(board_set="different", split="train")
    groups.update(other_groups)
    with pytest.raises(ValueError, match="session"):
        collect([export, other], tmp_path, groups)


def test_temperature_changes_confidence_not_classes_and_handles_extreme_logits():
    logits = np.array([[1000.0] + [-1000.0] * 11, [2.0, 3.0] + [0.0] * 10])
    np.testing.assert_array_equal(
        probabilities(logits).argmax(1), probabilities(logits, 2).argmax(1)
    )
    assert np.isfinite(diagnostics(logits, [1, 0])["nll"])
    temperature = fit_temperature(logits, [1, 0])
    assert diagnostics(logits, [1, 0], temperature)["nll"] <= diagnostics(logits, [1, 0])["nll"]
    for bad in (0, -1, float("nan")):
        with pytest.raises(ValueError):
            probabilities(logits, bad)


def test_calibration_never_fits_test_or_splits_one_capture_group():
    rows = [{"group_id": str(g), "label": 0, "logits": [2] + [0] * 11} for g in range(6)]
    with pytest.raises(ValueError, match="validation"):
        evaluate_validation({"split": "test", "records": rows})
    with pytest.raises(ValueError, match="four"):
        evaluate_validation({"split": "valid", "records": rows[:2]})
    report = evaluate_validation({"split": "valid", "records": rows})
    assert not set(report["fit_groups"]) & set(report["evaluation_groups"])
    assert not report["promoted"]


def test_geometry_trials_do_not_mutate_predictions_or_invent_missing_pieces():
    prediction = {"boxes": [[10, 10, 90, 90]], "labels": [1], "scores": [0.9]}
    original = copy.deepcopy(prediction)
    baseline = remap(prediction, 800, 800, 0.5)
    remap(prediction, 800, 800, 0.8)
    assert prediction == original
    sensitive = copy.deepcopy(baseline)
    sensitive["board"][1][1] = "black-king"
    trial = extra_review(baseline, sensitive)
    assert trial["board"][1][1] is None
    assert trial["reviewSquares"][-1]["row"] == 1
    assert not baseline["reviewSquares"]
