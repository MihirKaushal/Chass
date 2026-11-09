import copy
import json

import pytest

from scanner.ml.merge import manifest_for, partition
from scanner.ml.merge_evaluate import decision, paired_bootstrap, summarize
from scanner.ml.merge_report import verification
from scanner.ml.transfer import sampling_weights, validate_transfer
from scanner.ml.verify_onnx import validation_records


def test_report_does_not_claim_missing_or_failed_parity_checks(tmp_path):
    output = tmp_path / "report"
    output.mkdir()
    assert verification(tmp_path, output) == []
    parity = {
        "images": 40,
        "board_and_review_parity": True,
        "top_three_label_parity": False,
        "max_score_difference": 0.01,
        "max_box_difference_pixels": 0.001,
    }
    (tmp_path / "onnx-parity.json").write_text(json.dumps(parity))
    lines = verification(tmp_path, output)
    assert "ONNX parity passed: **False**" in "\n".join(lines)
    assert json.loads((output / "onnx-parity.json").read_text()) == parity


def row(index, source=1, split="train", group=None):
    return {
        "id": index,
        "key": str(index),
        "source_index": source,
        "source_dataset": str(source),
        "source_group": group or str(index),
        "pixel_sha256": str(index),
        "split": split,
        "boxes": [[0, 0, 1, 1]],
        "labels": [1],
    }


def test_related_added_training_is_quarantined_not_moved_to_test():
    rows = [row(0, source=0), row(1), row(2, split="test")]
    retained, excluded = partition(rows, [{"first": 1, "second": 2}])
    assert [r["id"] for r in retained] == [0, 2]
    assert excluded[0]["key"] == "1"
    assert rows[1]["split"] == "train"


def test_frozen_base_leakage_requires_manual_review():
    with pytest.raises(ValueError, match="base splits"):
        partition([row(0, source=0), row(1, source=0, split="test")], [{"first": 0, "second": 1}])
    with pytest.raises(ValueError, match="Added holdout"):
        partition([row(0, source=0), row(1, split="test")], [{"first": 0, "second": 1}])


def test_added_pixel_duplicates_removed_but_label_conflicts_fail():
    rows = [row(0, source=0), row(1)]
    rows[1]["pixel_sha256"] = "0"
    retained, excluded = partition(rows, [])
    assert len(retained) == len(excluded) == 1
    rows[1]["labels"] = [2]
    with pytest.raises(ValueError, match="conflicting annotations"):
        partition(rows, [])


def test_control_and_merged_holdouts_are_identical(tmp_path):
    rows, _ = partition([row(0, source=0), row(1), row(2, split="valid"), row(3, split="test")], [])
    control = manifest_for(rows, tmp_path, [], "control")
    merged = manifest_for(rows, tmp_path, [], "merged")
    assert [r for r in control["records"] if r["split"] != "train"] == [
        r for r in merged["records"] if r["split"] != "train"
    ]
    assert len(merged["records"]) == len(control["records"]) + 1


def test_sampling_weights_balance_sources_and_classes_without_changing_budget():
    rows = (
        [{"source_dataset": "a", "label": 1}] * 90
        + [{"source_dataset": "b", "label": 1}] * 9
        + [{"source_dataset": "b", "label": 2}]
    )
    for multipliers in (None, {1: 2}):
        weights = sampling_weights(rows, {"a": 0.75, "b": 0.25}, multipliers)
        assert sum(weights[:90]) == pytest.approx(0.75)
        assert sum(weights[90:]) == pytest.approx(0.25)
    with pytest.raises(ValueError, match="positive weights"):
        sampling_weights(rows, {"a": 1})


def test_transfer_never_relabels_or_moves_previously_seen_records(monkeypatch):
    source = {
        "fingerprint": "original",
        "records": [{"sha256": "photo", "split": "train", "boxes": [], "labels": []}],
    }
    monkeypatch.setattr("scanner.ml.transfer.read_manifest", lambda path: source)
    target = copy.deepcopy(source)
    validate_transfer({"dataset_fingerprint": "original"}, target, "manifest")
    target["records"][0]["split"] = "test"
    with pytest.raises(ValueError, match="preserve"):
        validate_transfer({"dataset_fingerprint": "original"}, target, "manifest")
    with pytest.raises(ValueError, match="source manifest differ"):
        validate_transfer({"dataset_fingerprint": "wrong"}, source, "manifest")


def test_source_macro_metric_does_not_hide_failure_on_small_source():
    records = [
        dict(row(0, source=0), iscrowd=[0], evaluation_group="a"),
        dict(row(1), iscrowd=[0], evaluation_group="b"),
    ]
    predictions = [
        {"image_id": 0, "boxes": [[0, 0, 1, 1]], "labels": [1], "scores": [0.9]},
        {"image_id": 1, "boxes": [], "labels": [], "scores": []},
    ]
    metrics = summarize(predictions, records, 0.2)
    assert metrics["macro_source_typed_f1"] == 0.5
    assert metrics["per_source"]["1"]["missed_pieces"] == 1
    assert metrics["combined"]["square_metrics"]["exact_board_accuracy"] is None


def test_bootstrap_keeps_paired_groups_and_refuses_different_ground_truth():
    control = [
        {
            "image_id": i,
            "source": str(i // 2),
            "group": str(i),
            "annotated_pieces": 10,
            "predictions": 10,
            "correct_type_color": 5,
        }
        for i in range(4)
    ]
    candidate = [{**r, "correct_type_color": 8} for r in control]
    result = paired_bootstrap(candidate, control, repetitions=100)
    assert result["macro_typed_f1_delta_95_percentile_interval"] == pytest.approx([0.3, 0.3])
    with pytest.raises(ValueError, match="identical ordered"):
        paired_bootstrap(candidate[::-1], control)
    shared_candidate = [{**r, "group": "shared"} for r in candidate]
    shared_control = [{**r, "group": "shared"} for r in control]
    with pytest.raises(ValueError, match="shared cross-source group"):
        paired_bootstrap(shared_candidate, shared_control)


def test_promotion_rejects_regression_even_with_larger_average():
    baseline = {
        "macro_source_typed_f1": 0.8,
        "per_source": {
            "a": {
                "typed_piece_recall": 0.8,
                "typed_prediction_precision": 0.8,
                "per_type": [{"piece": "king", "correct": 8, "support": 10}],
            }
        },
    }
    candidate = copy.deepcopy(baseline)
    candidate["macro_source_typed_f1"] = 0.85
    candidate["per_source"]["a"]["typed_piece_recall"] = 0.7
    result = decision(
        {
            "control": {"test": baseline},
            "deployed": {"test": baseline},
            "merged": {"test": candidate},
        },
        {"macro_typed_f1_delta_95_percentile_interval": [0.01, 0.1]},
        {
            "minimum_macro_typed_f1_gain": 0.01,
            "maximum_source_recall_or_precision_drop": 0.02,
            "maximum_king_recall_drop": 0.02,
        },
    )
    assert not result["accuracy_gate_passed"]
    assert any("typed_piece_recall regressed" in message for message in result["failures"])
    assert not result["deployed_models_changed"]


def test_parity_sampling_covers_each_source_without_using_test_images():
    records = (
        [row(i, source=0, split="valid") for i in range(10)]
        + [row(10 + i, split="valid") for i in range(3)]
        + [row(20, split="test")]
    )
    selected = validation_records({"records": records}, 2, per_source=True)
    assert [r["id"] for r in selected] == [0, 9, 10, 12]
    assert all(r["split"] == "valid" for r in selected)
