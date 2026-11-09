import hashlib
import json
import shutil
from unittest.mock import patch

import pytest
import torch

from scanner.ml.data import (
    CLASSES,
    CocoPieces,
    prepare_dataset,
    read_manifest,
    resolve_image,
    source_group,
)

from .conftest import change_annotations


def test_prepare_remaps_categories_and_preserves_originals(dataset_root, tmp_path):
    files = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in dataset_root.rglob("*")
        if path.is_file()
    }
    output = tmp_path / "prepared"
    report = prepare_dataset(dataset_root, output)
    manifest = read_manifest(output / "manifest.json")
    assert report["valid"] and report["total_images"] == 3
    assert report["source_groups"] == 3
    assert manifest["records"][0]["labels"] == [CLASSES.index("white-rook")]
    assert manifest["records"][0]["boxes"] == [[5, 6, 15, 18]]
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files} == files
    assert prepare_dataset(dataset_root, output)["fingerprint"] == report["fingerprint"]
    assert "white-pawn" in report["splits"]["train"]["missing_classes"]


@pytest.mark.parametrize(
    "change, reason",
    [
        (lambda data: data["annotations"][0].update(bbox=[60, 1, 10, 10]), "out-of-bounds"),
        (lambda data: data["annotations"][0].update(bbox=[1, 1, -2, 3]), "out-of-bounds"),
        (
            lambda data: data["annotations"][0].update(bbox=[1, float("nan"), 2, 3]),
            "invalid category/bounding box",
        ),
        (
            lambda data: data["annotations"][0].update(category_id=0),
            "invalid category/bounding box",
        ),
        (lambda data: data["annotations"][0].update(image_id=123), "missing image IDs"),
        (
            lambda data: data["annotations"].append(dict(data["annotations"][0])),
            "duplicate annotation",
        ),
        (lambda data: data["images"].append(dict(data["images"][0])), "duplicate image"),
        (lambda data: data["images"][0].update(width=100), "dimensions"),
        (lambda data: data["images"][0].update(file_name="missing.jpg"), "missing.jpg"),
        (lambda data: data["annotations"][0].update(iscrowd=1), "crowd regions"),
        (lambda data: data["categories"][1].update(name="dragon"), "unsupported categories"),
        (lambda data: data["categories"].append(dict(data["categories"][0])), "duplicate category"),
        (
            lambda data: data["annotations"].append({**data["annotations"][0], "id": 9}),
            "duplicate piece box",
        ),
    ],
)
def test_bad_labels_are_rejected(dataset_root, tmp_path, change, reason):
    change_annotations(dataset_root, change)
    with pytest.raises(ValueError, match="audit failed"):
        prepare_dataset(dataset_root, tmp_path / "prepared")
    audit = json.loads((tmp_path / "prepared/audit.json").read_text())
    assert any(reason in message for message in audit["errors"])


@pytest.mark.parametrize("kind", ["source", "hash"])
def test_split_leakage_is_rejected(dataset_root, tmp_path, kind):
    if kind == "hash":
        shutil.copyfile(
            next((dataset_root / "train").glob("*.jpg")),
            next((dataset_root / "test").glob("*.jpg")),
        )
    else:
        source = next((dataset_root / "test").glob("*.jpg"))
        source.rename(source.with_name("board-train.rf.different.jpg"))
        change_annotations(
            dataset_root,
            lambda data: data["images"][0].update(file_name="board-train.rf.different.jpg"),
            "test",
        )
    with pytest.raises(ValueError, match="audit failed"):
        prepare_dataset(dataset_root, tmp_path / "prepared")
    assert "Leakage:" in (tmp_path / "prepared/audit.json").read_text()


def test_manifest_rejects_changed_images_and_records(dataset_root, tmp_path):
    output = tmp_path / "prepared"
    prepare_dataset(dataset_root, output)
    path = output / "manifest.json"
    original = path.read_text()
    manifest = json.loads(original)
    manifest["records"][0]["labels"] = [1]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="fingerprint"):
        read_manifest(path)
    path.write_text(original)
    next((dataset_root / "train").glob("*.jpg")).write_bytes(b"changed")
    with pytest.raises(ValueError, match="Image changed"):
        read_manifest(path)


def test_missing_split_and_path_escape(dataset_root, tmp_path):
    (dataset_root / "valid/_annotations.coco.json").unlink()
    with pytest.raises(ValueError, match="audit failed"):
        prepare_dataset(dataset_root, tmp_path / "prepared")
    with pytest.raises(ValueError, match="escapes"):
        resolve_image(dataset_root, "../../outside.jpg")


def test_training_flip_moves_boxes_but_evaluation_is_unmodified(dataset_root, tmp_path):
    prepare_dataset(dataset_root, tmp_path / "prepared")
    manifest = read_manifest(tmp_path / "prepared/manifest.json")
    dataset = CocoPieces(manifest, "train", augment=True)
    with patch("random.random", return_value=0.0):
        image, target = dataset[0]
    assert image.shape == (3, 48, 64)
    assert target["boxes"].tolist() == [[49, 6, 59, 18]]
    assert target["labels"].dtype == torch.int64
    assert CocoPieces(manifest, "valid")[0][1]["boxes"].tolist() == [[5, 6, 15, 18]]
    with pytest.raises(ValueError, match="training split"):
        CocoPieces(manifest, "test", augment=True)


def test_source_group_keeps_original_identity():
    assert source_group("IMG_0123_jpg.rf.abcd.jpg") == "IMG_0123_jpg"
    assert source_group("IMG_0123_jpg.rf.efgh.jpg") == "IMG_0123_jpg"
    assert source_group("original.jpg") == "original.jpg"


def test_detector_resize_scales_targets_without_changing_records(dataset_root, tmp_path):
    prepare_dataset(dataset_root, tmp_path / "prepared")
    manifest = read_manifest(tmp_path / "prepared/manifest.json")
    image, target = CocoPieces(manifest, "valid", input_size=320)[0]
    assert image.shape == (3, 320, 320)
    torch.testing.assert_close(target["boxes"], torch.tensor([[25.0, 40.0, 75.0, 120.0]]))
    torch.testing.assert_close(target["area"], torch.tensor([4000.0]))
    assert manifest["records"][0]["boxes"] == [[5, 6, 15, 18]]
    for size in (0, -1, True, 320.5):
        with pytest.raises(ValueError, match="positive integer"):
            CocoPieces(manifest, "valid", input_size=size)


def test_resized_flip_keeps_boxes_in_image_coordinates(dataset_root, tmp_path):
    prepare_dataset(dataset_root, tmp_path / "prepared")
    manifest = read_manifest(tmp_path / "prepared/manifest.json")
    with patch("random.random", return_value=0.0):
        _, target = CocoPieces(manifest, "train", augment=True, input_size=320)[0]
    torch.testing.assert_close(target["boxes"], torch.tensor([[245.0, 40.0, 295.0, 120.0]]))


def test_failed_reaudit_blocks_a_stale_manifest(dataset_root, tmp_path):
    output = tmp_path / "prepared"
    prepare_dataset(dataset_root, output)
    change_annotations(
        dataset_root, lambda data: data["annotations"][0].update(bbox=[60, 1, 10, 10])
    )
    with pytest.raises(ValueError, match="audit failed"):
        prepare_dataset(dataset_root, output)
    with pytest.raises(ValueError, match="latest dataset audit failed"):
        read_manifest(output / "manifest.json")
