import hashlib
import json

import pytest

from scanner.ml.board_collection import collect


def example(tmp_path, suffix=""):
    photo = tmp_path / f"photo{suffix}.jpg"
    photo.write_bytes(b"photo" + suffix.encode())
    digest = hashlib.sha256(photo.read_bytes()).hexdigest()
    record = {
        "image_id": digest,
        "image_sha256": digest,
        "orientation": "white_bottom",
        "verified": True,
        "board": [[None] * 8 for _ in range(8)],
    }
    export = tmp_path / f"labels{suffix}.json"
    export.write_text(json.dumps({"records": [record]}))
    group = {digest: {"split": "test", "board_set": "wooden", "session": "day1"}}
    return export, digest, group


def test_duplicate_exports_are_deduplicated(tmp_path):
    export, _, group = example(tmp_path)
    assert len(collect([export, export], tmp_path, group)["records"]) == 1


def test_physical_set_cannot_leak_between_splits(tmp_path):
    first, _, groups = example(tmp_path)
    second, digest, extra = example(tmp_path, "2")
    groups.update(extra)
    groups[digest]["split"] = "train"
    with pytest.raises(ValueError, match="cannot cross"):
        collect([first, second], tmp_path, groups)


def test_requires_verified_labels_matching_photo_and_group(tmp_path):
    export, digest, groups = example(tmp_path)
    with pytest.raises(ValueError, match="Assign"):
        collect([export], tmp_path, {})
    data = json.loads(export.read_text())
    data["records"][0]["verified"] = False
    export.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="manually verified"):
        collect([export], tmp_path, groups)
    (tmp_path / "photo.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="exact prepared photo"):
        collect([export], tmp_path, groups)
