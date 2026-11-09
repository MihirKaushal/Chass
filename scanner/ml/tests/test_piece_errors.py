from scanner.ml.piece_errors import analyze


def test_confusion_duplicates_background_and_misses_are_distinct():
    gt = {
        "id": 1,
        "boxes": [[0, 0, 10, 10], [20, 0, 30, 10]],
        "labels": [12, 10],
        "iscrowd": [0, 0],
    }
    pred = {
        "image_id": 1,
        "boxes": [[0, 0, 10, 10], [0, 0, 10, 10], [25, 0, 35, 10], [100, 0, 110, 10]],
        "labels": [11, 12, 10, 2],
        "scores": [0.9, 0.8, 0.7, 0.6],
    }
    result, events = analyze([pred], [gt], 0.25)
    assert result["totals"] == {
        "correct": 0,
        "wrong_label": 1,
        "missed": 1,
        "duplicate_candidate": 1,
        "localization_candidate": 1,
        "background_candidate": 1,
    }
    classes = {r["piece"]: r for r in result["by_actual_class"]}
    assert classes["white-rook"]["located"] == 1
    assert classes["white-rook"]["conditional_type_color_accuracy"] == 0
    assert classes["white-pawn"]["miss_rate"] == 1
    assert classes["black-rook"]["miss_rate"] is None
    assert result["confusions"] == [
        {"actual": "white-rook", "predicted": "white-queen", "count": 1}
    ]
    assert len(events) == 5


def test_duplicate_uses_an_already_matched_box_only():
    gt = {"id": 1, "boxes": [[0, 0, 10, 10], [2, 0, 12, 10]], "labels": [12, 11], "iscrowd": [0, 0]}
    pred = {"image_id": 1, "boxes": gt["boxes"], "labels": gt["labels"], "scores": [0.9, 0.8]}
    result, _ = analyze([pred], [gt], 0.25)
    assert result["totals"]["correct"] == 2
    assert result["totals"]["duplicate_candidate"] == 0


def test_color_errors_stay_errors_in_type_aggregate():
    gt = {"id": 1, "boxes": [[0, 0, 10, 10]], "labels": [12], "iscrowd": [0]}
    pred = {"image_id": 1, "boxes": gt["boxes"], "labels": [6], "scores": [0.9]}
    result, _ = analyze([pred], [gt], 0.25)
    rook = next(r for r in result["by_actual_type"] if r["piece"] == "rook")
    assert rook["conditional_type_color_accuracy"] == 0


def test_empty_ground_truth_predictions_are_background_candidates():
    gt = {"id": 1, "boxes": [], "labels": [], "iscrowd": []}
    pred = {"image_id": 1, "boxes": [[0, 0, 10, 10]], "labels": [6], "scores": [0.9]}
    result, events = analyze([pred], [gt], 0.25)
    assert result["totals"]["background_candidate"] == 1
    assert events[0]["actual_or_nearest"] is None
    assert events[0]["target_box"] is None
