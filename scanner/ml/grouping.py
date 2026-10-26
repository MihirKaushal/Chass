"""Conservative image identity and capture grouping, independent of model predictions."""

import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from PIL import Image


class Groups:
    def __init__(self, size):
        self.parents = list(range(size))

    def find(self, index):
        while self.parents[index] != index:
            self.parents[index] = self.parents[self.parents[index]]
            index = self.parents[index]
        return index

    def join(self, first, second):
        first, second = self.find(first), self.find(second)
        self.parents[max(first, second)] = min(first, second)


def capture_group(name):
    match = re.search(r"(?<!\d)(20\d{6})[_-]?(\d{6})(?!\d)", name)
    if match:
        try:
            day = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S").date()
            return f"capture-day:{day}"
        except ValueError:
            pass
    match = re.search(r"(?<!\d)(1[56]\d{11})(?!\d)", name)
    if match:
        day = datetime.fromtimestamp(int(match[1]) / 1000, timezone.utc).date()
        return f"capture-day:{day}"
    # Unknown camera families stay together rather than claiming every frame is independent.
    prefix = re.match(r"[A-Za-z]+", name)
    return f"unknown-family:{prefix[0].lower() if prefix else 'numeric'}"


def thumbnail_features(image):
    thumb = np.asarray(image.convert("L").resize((96, 96), Image.Resampling.LANCZOS))
    coordinate = np.arange(32)
    basis = np.cos(np.pi * (2 * coordinate[None, :] + 1) * coordinate[:, None] / 64)
    hashes = []
    small = np.asarray(image.convert("L").resize((32, 32)), dtype=float)
    for mirrored in (False, True):
        base = np.fliplr(small) if mirrored else small
        for angle in range(4):
            frequency = (basis @ np.rot90(base, angle) @ basis.T)[:8, :8].ravel()
            bits = frequency > np.median(frequency[1:])
            bits[0] = False
            hashes.append(int.from_bytes(np.packbits(bits).tobytes(), "big"))
    return thumb, hashes


def near_pairs(rows, *, max_hamming=4):
    """Return perceptual candidates and matching transform; these are not automatic deletions."""
    if not rows:
        return []
    hashes = np.asarray([row["phashes"] for row in rows], dtype=np.uint64)
    result = []
    for left in range(len(rows)):
        distances = np.bitwise_count(hashes[left, 0] ^ hashes[left + 1 :])
        for offset in np.flatnonzero((distances <= max_hamming).any(axis=1)):
            transform = int(distances[offset].argmin())
            right = left + 1 + int(offset)
            thumb = rows[right]["thumb"]
            if transform >= 4:
                thumb = np.fliplr(thumb)
            thumb = np.rot90(thumb, transform % 4)
            first = rows[left]["thumb"].astype(float)
            second = thumb.astype(float)
            correlation = (
                float(np.corrcoef(first.ravel(), second.ravel())[0, 1])
                if min(first.std(), second.std()) > 0
                else 0
            )
            mae = float(np.abs(first - second).mean())
            if correlation >= 0.985 and mae <= 8:
                result.append(
                    {
                        "first": left,
                        "second": right,
                        "transform": transform,
                        "hamming": int(distances[offset, transform]),
                        "mae": mae,
                        "correlation": correlation,
                    }
                )
    return result


def assign_splits(rows, pairs, seed=42, *, fixed_capture_splits=None):
    groups = Groups(len(rows))
    for key in ("capture_group", "source_group", "pixel_sha256"):
        seen = {}
        for index, row in enumerate(rows):
            if row[key] in seen:
                groups.join(index, seen[row[key]])
            seen[row[key]] = index
    for pair in pairs:
        groups.join(pair["first"], pair["second"])
    members = defaultdict(list)
    for index in range(len(rows)):
        members[groups.find(index)].append(index)
    if len(members) < 3:
        raise ValueError("At least three independent capture groups are required for safe splits.")
    if fixed_capture_splits is not None:
        return preserve_capture_splits(rows, members, fixed_capture_splits)
    fractions = np.array([0.7, 0.15, 0.15])
    target = fractions * len(rows)
    counts = np.zeros(3)
    sizes = sorted(
        members.values(),
        key=lambda indices: (
            -len(indices),
            hashlib.sha256(f"{seed}:{rows[indices[0]]['key']}".encode()).hexdigest(),
        ),
    )
    assignments = []
    for position, indices in enumerate(sizes):
        costs = []
        for split in range(3):
            next_counts = counts.copy()
            next_counts[split] += len(indices)
            costs.append(float((((next_counts - target) / target) ** 2).sum()))
        # Reserve one complete group per split even when only three groups exist.
        split = position if position < 3 else int(np.argmin(costs))
        counts[split] += len(indices)
        assignments.append(
            {
                "indices": indices,
                "split": split,
                "labels": {
                    annotation["label"]
                    for index in indices
                    for annotation in rows[index].get("annotations", [])
                },
            }
        )
    labels = sorted(set().union(*(group["labels"] for group in assignments)))
    while True:
        support = [
            Counter(
                label
                for group in assignments
                if group["split"] == split
                for label in group["labels"]
            )
            for split in range(3)
        ]
        missing = [
            (split, label) for split in range(3) for label in labels if not support[split][label]
        ]
        if not missing:
            break
        destination, label = missing[0]
        candidates = []
        for position, group in enumerate(assignments):
            donor = group["split"]
            if (
                donor == destination
                or label not in group["labels"]
                or any(support[donor][item] <= 1 for item in group["labels"])
            ):
                continue
            moved = counts.copy()
            moved[donor] -= len(group["indices"])
            moved[destination] += len(group["indices"])
            candidates.append((float((((moved - target) / target) ** 2).sum()), position, moved))
        if not candidates:
            raise ValueError(
                f"Cannot give every split class {label} without breaking capture groups. More independent labeled groups are needed."
            )
        _, position, counts = min(candidates, key=lambda candidate: (candidate[0], candidate[1]))
        assignments[position]["split"] = destination
    for group in assignments:
        indices, split = group["indices"], group["split"]
        group_id = hashlib.sha256(
            "\n".join(sorted(rows[index]["key"] for index in indices)).encode()
        ).hexdigest()[:16]
        for index in indices:
            rows[index]["split"] = ("train", "valid", "test")[split]
            rows[index]["split_group"] = group_id
    if any(count == 0 for count in counts):
        raise ValueError(
            "Capture grouping produced an empty split; review grouping instead of splitting related frames."
        )
    return {
        "target_fractions": fractions.tolist(),
        "counts": dict(zip(("train", "valid", "test"), map(int, counts), strict=True)),
        "groups": len(members),
        "method": "Capture day/family, source name, pixel identity and perceptual candidates stay together.",
    }


def preserve_capture_splits(rows, members, fixed):
    """Correct labels without moving previously exposed validation captures into test."""
    splits = ("train", "valid", "test")
    counts = Counter()
    coverage = {split: set() for split in splits}
    for indices in members.values():
        assignments = {fixed.get(rows[index]["capture_group"]) for index in indices}
        if len(assignments) != 1 or not assignments.issubset(splits):
            raise ValueError(
                "Fixed capture splits are missing, invalid, or conflict within a related group."
            )
        split = assignments.pop()
        group_id = hashlib.sha256(
            "\n".join(sorted(rows[index]["key"] for index in indices)).encode()
        ).hexdigest()[:16]
        for index in indices:
            rows[index]["split"] = split
            rows[index]["split_group"] = group_id
            counts[split] += 1
            coverage[split].update(a["label"] for a in rows[index].get("annotations", []))
    labels = set().union(*coverage.values())
    if any(not counts[split] or coverage[split] != labels for split in splits):
        raise ValueError(
            "Fixed capture splits require nonempty splits with every class represented."
        )
    return {
        "target_fractions": [0.7, 0.15, 0.15],
        "counts": {split: counts[split] for split in splits},
        "groups": len(members),
        "method": "Preserved prior capture assignments; all related frames must agree. No validation-to-test reassignment.",
    }
