import json
from copy import deepcopy
from datetime import date

import pytest

from scanner.ml.benchmark import export, piece_diagnostics, snapshot
from scanner.ml.metrics import operating_metrics


def record(labels=None):
    return {
        "id": 1,
        "boxes": [[0, 0, 10, 10]],
        "labels": [12] if labels is None else labels,
        "iscrowd": [0],
    }


def prediction(labels=None, scores=None, boxes=None):
    return {
        "image_id": 1,
        "boxes": [[0, 0, 10, 10]] if boxes is None else boxes,
        "labels": [12] if labels is None else labels,
        "scores": [0.9] if scores is None else scores,
    }


def test_perfect_box_does_not_invent_square_accuracy():
    result = piece_diagnostics([prediction()], [record()], 0.25)
    assert result["localization_precision"] == result["localization_recall"] == 1
    assert result["conditional_type_color_accuracy"] == result["typed_piece_recall"] == 1
    assert result["square_metrics"]["occupancy_accuracy"] is None
    assert result["square_metrics"]["overall_13_class_square_accuracy"] is None


@pytest.mark.parametrize(
    "label,type_accuracy,color_accuracy",
    [(6, 1, 0), (11, 0, 1), (5, 0, 0)],
)
def test_type_and_color_are_measured_separately(label, type_accuracy, color_accuracy):
    result = piece_diagnostics([prediction(labels=[label])], [record()], 0.25)
    assert result["localization_recall"] == 1
    assert result["conditional_type_accuracy"] == type_accuracy
    assert result["conditional_color_accuracy"] == color_accuracy
    assert result["conditional_type_color_accuracy"] == 0


def test_high_confidence_wrong_label_cannot_be_rescued_by_alternative_label():
    pred = prediction(labels=[11, 12], scores=[0.9, 0.8], boxes=[[0, 0, 10, 10]] * 2)
    result = piece_diagnostics([pred], [record()], 0.25)
    assert result["localized_pieces"] == result["unmatched_predictions"] == 1
    assert result["localization_precision"] == 0.5
    assert result["conditional_type_color_accuracy"] == 0
    # Standard detection metrics permit class-aware matching; these diagnostics do not.
    assert operating_metrics([pred], [record()], 0.25)["tp"] == 1


def test_false_alarm_is_not_a_correct_typed_prediction():
    pred = prediction(labels=[12, 12], scores=[0.8, 0.9], boxes=[[0, 0, 10, 10], [30, 0, 40, 10]])
    result = piece_diagnostics([pred], [record()], 0.25)
    assert result["conditional_type_color_accuracy"] == 1
    assert result["typed_prediction_precision"] == 0.5
    assert result["typed_piece_recall"] == 1


def test_missed_pieces_do_not_enter_conditional_accuracy():
    result = piece_diagnostics([prediction(scores=[0.24])], [record()], 0.25)
    assert result["localization_precision"] is None
    assert result["localization_recall"] == result["typed_piece_recall"] == 0
    assert result["conditional_type_color_accuracy"] is None
    assert result["missed_pieces"] == 1


def test_empty_image_and_no_predictions_are_not_artificially_perfect():
    gt = {"id": 1, "boxes": [], "labels": [], "iscrowd": []}
    result = piece_diagnostics([prediction(labels=[], scores=[], boxes=[])], [gt], 0.25)
    assert result["localization_recall"] is None
    assert result["conditional_type_color_accuracy"] is None
    assert result["square_metrics"]["exact_board_accuracy"] is None


def test_threshold_is_inclusive_and_counts_are_one_to_one():
    pred = prediction(labels=[12, 12], scores=[0.25, 0.24], boxes=[[0, 0, 10, 10]] * 2)
    result = piece_diagnostics([pred], [record()], 0.25)
    assert result["predictions"] == result["localized_pieces"] == 1


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unexpected"])
def test_invalid_image_coverage_is_rejected(kind):
    preds = [] if kind == "missing" else [prediction(), prediction()]
    if kind == "unexpected":
        preds[1]["image_id"] = 2
    with pytest.raises(ValueError, match="exactly once"):
        piece_diagnostics(preds, [record()], 0.25)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_prediction_is_rejected(score):
    with pytest.raises(ValueError, match="Invalid piece detection"):
        piece_diagnostics([prediction(scores=[score])], [record()], 0.25)


def test_snapshot_export_preserves_nulls_and_will_not_overwrite(tmp_path):
    row = piece_diagnostics([prediction()], [record()], 0.25)
    snapshot = {
        "run_id": "unit-test",
        "training_date": "2026-10-25",
        "recorded_on": "2026-10-26",
        "architecture": "test",
        "checkpoint_sha256": "test",
        "dataset": {"fingerprint": "test", "splits": {"train": {"images": 1, "annotations": 1}}},
        "training": {"best_epoch": 1},
        "splits": {
            "test": {
                "piece_diagnostics": row,
                "detection": {
                    key: 1.0
                    for key in (
                        "map50",
                        "map50_95",
                        "precision",
                        "recall",
                        "f1",
                        "exact_detection_image_rate",
                    )
                },
            }
        },
    }
    original = deepcopy(snapshot)
    path = tmp_path / "run.json"
    export(snapshot, path)
    assert snapshot == original
    assert '"occupancy_accuracy": null' in path.read_text()
    assert "overall_13_class_square_accuracy" in path.with_suffix(".csv").read_text()
    with pytest.raises(ValueError, match="immutable"):
        export(snapshot, path)


def test_csv_output_cannot_overwrite_json_snapshot(tmp_path):
    with pytest.raises(ValueError, match=".json extension"):
        export({}, tmp_path / "run.csv")


@pytest.mark.parametrize("threshold,iou", [(float("nan"), 0.5), (-1, 0.5), (0.25, 0), (0.25, 2)])
def test_invalid_matching_parameters(threshold, iou):
    with pytest.raises(ValueError):
        piece_diagnostics([prediction()], [record()], threshold, iou)


@pytest.mark.parametrize(
    "change,error",
    [
        ("dataset", "different datasets"),
        ("threshold", "frozen validation"),
        ("checkpoint", "same checkpoint"),
        ("evaluation", "fingerprints differ"),
        ("counts", "recorded detection counts"),
        (None, None),
    ],
)
def test_snapshot_checks_provenance_and_reproduces_saved_counts(
    tmp_path, monkeypatch, change, error
):
    valid, test = record(), record()
    valid["split"], test["split"], test["id"] = "valid", "test", 2
    manifest = {"fingerprint": "dataset", "records": [valid, test]}
    monkeypatch.setattr("scanner.ml.benchmark.read_manifest", lambda path: manifest)
    source = {
        "run_date": "2026-10-25",
        "architecture": "test",
        "dataset": {"fingerprint": "dataset"},
        "training": {},
        "environment": {},
    }
    for key, gt in (("validation", valid), ("test", test)):
        pred = prediction()
        pred["image_id"] = gt["id"]
        folder = tmp_path / key
        folder.mkdir()
        (folder / "predictions.json").write_text(json.dumps([pred]))
        source[key] = {
            **operating_metrics([pred], [gt], 0.25),
            "dataset_fingerprint": "dataset",
            "checkpoint_sha256": "checkpoint",
        }
    if change == "dataset":
        source["dataset"]["fingerprint"] = "different"
    elif change == "threshold":
        source["test"]["threshold"] = 0.5
    elif change == "checkpoint":
        source["test"]["checkpoint_sha256"] = "different"
    elif change == "evaluation":
        source["test"]["dataset_fingerprint"] = "different"
    elif change == "counts":
        source["test"]["tp"] = 0
    results = tmp_path / "results.json"
    results.write_text(json.dumps(source))

    def generate():
        return snapshot(results, tmp_path / "manifest.json", tmp_path, "run", date(2026, 10, 26))

    if error:
        with pytest.raises(ValueError, match=error):
            generate()
    else:
        result = generate()
        assert result["splits"]["test"]["piece_diagnostics"]["correct_type_color"] == 1
        assert result["training_date"] == "2026-10-25"
        assert result["recorded_on"] == "2026-10-26"
