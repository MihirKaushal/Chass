"""Conservative square assignment for an already rectified, white-at-bottom board."""

from __future__ import annotations

import math
from collections import defaultdict

from .data import CLASSES


def assign_squares(
    prediction, width, height, *, classification_threshold=0.7, detection_threshold=0.5
):
    if width <= 0 or height <= 0:
        raise ValueError("Positive board image dimensions are required.")
    if not 0 <= classification_threshold <= 1 or not 0 <= detection_threshold <= 1:
        raise ValueError("Review thresholds must be between 0 and 1.")
    candidates = defaultdict(list)
    outside = 0
    for index, (box, label, score) in enumerate(
        zip(prediction["boxes"], prediction["labels"], prediction["scores"], strict=True)
    ):
        if (
            len(box) != 4
            or not all(math.isfinite(v) for v in box)
            or box[2] <= box[0]
            or box[3] <= box[1]
            or not 1 <= label < len(CLASSES)
        ):
            raise ValueError("Invalid square assignment proposal.")
        x, y = (box[0] + box[2]) / 2 / width * 8, (box[1] + box[3]) / 2 / height * 8
        if not 0 <= x < 8 or not 0 <= y < 8:
            outside += 1
            continue
        row, col = int(y), int(x)
        confidence = prediction.get("classifier_scores", prediction["scores"])[index]
        reasons = []
        if confidence < classification_threshold or score < detection_threshold:
            reasons.append("Low model confidence")
        if min(x % 1, 1 - x % 1, y % 1, 1 - y % 1) < 0.18:
            reasons.append("Piece center is close to a square boundary")
        if box[2] - box[0] > width / 8 * 1.2 or box[3] - box[1] > height / 8 * 1.2:
            reasons.append("Piece spans multiple squares; check its base")
        candidates[row, col].append(
            {
                "class": CLASSES[label],
                "score": score,
                "classifierScore": confidence,
                "reasons": reasons,
                "alternatives": prediction.get("alternatives", [[]] * len(prediction["boxes"]))[
                    index
                ],
            }
        )
    board, review, squares = [[None] * 8 for _ in range(8)], [], []
    for (row, col), options in sorted(candidates.items()):
        options.sort(key=lambda option: -option["score"])
        choice = options[0]
        reasons = list(choice["reasons"])
        if len(options) > 1:
            reasons.append("Multiple pieces mapped here; inspect this and neighboring squares")
        board[row][col] = choice["class"]
        label = f"{'abcdefgh'[col]}{8 - row}"
        squares.append({"row": row, "col": col, "label": label, "candidates": options})
        if reasons:
            review.append({"row": row, "col": col, "label": label, "reasons": reasons})
    return {
        "board": board,
        "reviewSquares": review,
        "squareCandidates": squares,
        "outsideDetections": outside,
        "reviewThresholds": {
            "classification": classification_threshold,
            "detection": detection_threshold,
        },
        "warnings": [
            "Experimental recognition: check all 64 squares, including empty squares.",
            "Square assignment uses box centers, not verified piece bases. Tall or tilted pieces can map to a neighboring square.",
        ],
    }


def square_metrics(predicted_boards, actual_boards):
    """Only accepts externally verified square labels, never detector boxes as truth."""
    if not actual_boards or len(predicted_boards) != len(actual_boards):
        raise ValueError("Supply matching, nonempty collections of verified boards.")
    counts = dict(
        squares=0,
        occupancy_correct=0,
        occupied=0,
        occupied_correct=0,
        exact_correct=0,
        exact_boards=0,
        missed=0,
        invented=0,
    )
    allowed = {None, *CLASSES[1:]}
    for predicted, actual in zip(predicted_boards, actual_boards, strict=True):
        for board in (predicted, actual):
            if (
                len(board) != 8
                or any(len(row) != 8 for row in board)
                or any(label not in allowed for row in board for label in row)
            ):
                raise ValueError("Each verified board must have 64 valid class/empty labels.")
        counts["exact_boards"] += predicted == actual
        for expected_row, found_row in zip(actual, predicted, strict=True):
            for expected, found in zip(expected_row, found_row, strict=True):
                counts["squares"] += 1
                counts["occupancy_correct"] += (expected is None) == (found is None)
                counts["exact_correct"] += expected == found
                counts["occupied"] += expected is not None
                counts["occupied_correct"] += expected is not None and expected == found
                counts["missed"] += expected is not None and found is None
                counts["invented"] += expected is None and found is not None
    return {
        **counts,
        "boards": len(actual_boards),
        "occupancy_accuracy": counts["occupancy_correct"] / counts["squares"],
        "occupied_square_type_color_accuracy": counts["occupied_correct"] / counts["occupied"]
        if counts["occupied"]
        else None,
        "overall_13_class_square_accuracy": counts["exact_correct"] / counts["squares"],
        "exact_board_accuracy": counts["exact_boards"] / len(actual_boards),
    }
