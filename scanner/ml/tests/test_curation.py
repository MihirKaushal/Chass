import json
from dataclasses import replace

import pytest
from PIL import Image

from scanner.ml.compare import compare_manifests
from scanner.ml.curation import (
    clean_annotations,
    curate,
    digest_bytes,
    equivalent_annotations,
    remove_copies,
)
from scanner.ml.data import CLASSES, SPLITS, read_manifest
from scanner.ml.datasets import TOP_DOWN
from scanner.ml.grouping import assign_splits, capture_group, near_pairs, thumbnail_features


def annotation(identifier, label=1, box=None):
    return {"id": identifier, "category_id": label, "bbox": box or [5, 6, 10, 12]}


def test_cleanup_removes_only_degenerate_or_redundant_boxes():
    source = [
        annotation(1),
        annotation(2, box=[5, 6, 0, 0]),
        annotation(3),
        annotation(4, box=[5.1, 6, 10, 12]),
    ]
    kept, changes, issues = clean_annotations(source, {1: "white-rook"}, (64, 48))
    assert [item["id"] for item in kept] == [1]
    assert [item["action"] for item in changes].count("duplicate_annotation_removed") == 2
    assert not issues
    assert len(source) == 4


@pytest.mark.parametrize("box", [[5, 6, -1, 2], [60, 6, 10, 12], [float("nan"), 6, 10, 12]])
def test_bad_geometry_is_quarantined_not_clipped(box):
    _, _, issues = clean_annotations([annotation(1, box=box)], {1: "white-rook"}, (64, 48))
    assert issues


def test_conflicting_classes_require_review_and_drops_are_scoped():
    source = [annotation(1), annotation(2, label=2)]
    categories = {1: "white-rook", 2: "black-rook"}
    assert clean_annotations(source, categories, (64, 48))[2]
    kept, changes, issues = clean_annotations(
        source, categories, (64, 48), drops={"2": "Reviewed incorrect color"}
    )
    assert len(kept) == 1 and changes[0]["action"] == "reviewed_annotation_removed" and not issues
    with pytest.raises(ValueError, match="absent annotation"):
        clean_annotations(source, categories, (64, 48), drops={"999": "not present"})


def test_empty_targets_are_not_invented_as_empty_board_labels():
    assert clean_annotations([annotation(1, box=[1, 2, 0, 0])], {1: "white-rook"}, (64, 48))[2]
    assert clean_annotations([], {1: "white-rook"}, (64, 48))[2]
    assert not clean_annotations([], {1: "white-rook"}, (64, 48), verified_empty=True)[2]


def test_ambiguous_overlap_is_reviewed_not_automatically_merged():
    source = [annotation(1), annotation(2, box=[7, 6, 10, 12])]
    kept, changes, issues = clean_annotations(
        source, {1: "white-rook"}, (64, 48), overlap_review_iou=0.5
    )
    assert len(kept) == 2 and not changes and issues


def sample_row(key, day, pixel, annotations=None):
    return {
        "key": key,
        "capture_group": day,
        "source_group": key,
        "pixel_sha256": pixel,
        "issues": [],
        "changes": [],
        "size": (64, 48),
        "annotations": annotations or [{"id": 1, "label": "white-rook", "bbox": [5, 6, 10, 12]}],
    }


def test_equal_pixels_with_conflicting_targets_are_not_arbitrarily_selected():
    first = sample_row("a", "day-a", "same")
    second = sample_row(
        "b", "day-b", "same", [{"id": 2, "label": "black-rook", "bbox": [5, 6, 10, 12]}]
    )
    kept, _ = remove_copies([first, second])
    assert kept == []
    assert first["issues"] and second["issues"]


def test_normalized_annotation_equivalence_respects_class_and_quarter_turns():
    first = {"size": (100, 200), "annotations": [{"label": "white-rook", "bbox": [10, 20, 20, 40]}]}
    second = {
        "size": (200, 100),
        "annotations": [{"label": "white-rook", "bbox": [140, 10, 40, 20]}],
    }
    assert equivalent_annotations(first, second, transform=1)
    assert not equivalent_annotations(first, second)
    second["annotations"][0]["label"] = "black-rook"
    assert not equivalent_annotations(first, second, transform=1)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("IMG_20220808_141918_jpg", "capture-day:2022-08-08"),
        ("IMG20210318213647_jpg", "capture-day:2021-03-18"),
        ("IMG_20229999_250099_jpg", "unknown-family:img"),
        ("Verse_2--3_jpg", "unknown-family:verse"),
    ],
)
def test_capture_grouping_is_conservative(name, expected):
    assert capture_group(name) == expected


def test_splits_keep_whole_components_and_are_deterministic():
    rows = [sample_row(str(i), f"day-{i // 2}", f"pixel-{i}") for i in range(12)]
    first = [dict(row) for row in rows]
    result = assign_splits(first, [{"first": 0, "second": 2}])
    assert result["groups"] == 5
    assert first[0]["split"] == first[1]["split"] == first[2]["split"] == first[3]["split"]
    assert set(row["split"] for row in first) == set(SPLITS)
    second = [dict(row) for row in rows]
    assign_splits(second, [{"first": 0, "second": 2}])
    assert [row["split"] for row in first] == [row["split"] for row in second]
    with pytest.raises(ValueError, match="three independent"):
        assign_splits(rows[:4], [])


def test_perceptual_features_find_quarter_turns():
    image = Image.new("RGB", (80, 120), "white")
    image.paste("black", (5, 10, 20, 50))
    image.paste("gray", (45, 60, 75, 110))
    first = thumbnail_features(image)
    second = thumbnail_features(image.transpose(Image.Transpose.ROTATE_90))
    pairs = near_pairs(
        [{"thumb": first[0], "phashes": first[1]}, {"thumb": second[0], "phashes": second[1]}]
    )
    assert len(pairs) == 1
    assert pairs[0]["correlation"] > 0.99


def make_source(tmp_path):
    root = tmp_path / "raw"
    hashes, annotations, overrides = [], {}, {}
    for index, split in enumerate(SPLITS):
        folder = root / split
        folder.mkdir(parents=True)
        filename = f"IMG_2022010{index + 1}_120000_jpg.rf.{split}.png"
        image = Image.new("RGB", (64, 48), (20 + index * 60, 40, 60))
        key = f"{split}/{filename}"
        if index == 0:
            image = image.transpose(Image.Transpose.ROTATE_90)
        image.save(folder / filename)
        digest = digest_bytes((folder / filename).read_bytes())
        hashes.append((key, digest))
        if index == 0:
            overrides[key] = {
                "sha256": digest,
                "rotation": "cw",
                "reason": "Synthetic known transform",
            }
        boxes = [
            annotation(i, label=i, box=[((i - 1) % 4) * 16, ((i - 1) // 4) * 16, 8, 10])
            for i in range(1, 13)
        ]
        boxes.extend(
            [annotation(13, label=1, box=boxes[0]["bbox"]), annotation(14, box=[2, 2, 0, 0])]
        )
        data = {
            "categories": [{"id": i, "name": name} for i, name in enumerate(CLASSES) if i],
            "images": [{"id": 1, "file_name": filename, "width": 64, "height": 48}],
            "annotations": [{**a, "image_id": 1} for a in boxes],
        }
        path = folder / "_annotations.coco.json"
        path.write_text(json.dumps(data))
        annotations[split] = digest_bytes(path.read_bytes())
    policy = {
        "format_version": 1,
        "dataset": "top-down",
        "seed": 42,
        "source_annotation_hashes": annotations,
        "source_images_hash": digest_bytes(json.dumps(sorted(hashes)).encode()),
        "images": overrides,
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    return replace(TOP_DOWN, root=root), path


def test_curation_is_end_to_end_audited_and_raw_bytes_are_unchanged(tmp_path):
    profile, policy = make_source(tmp_path)
    before = {str(p): digest_bytes(p.read_bytes()) for p in profile.root.rglob("*") if p.is_file()}
    output, report = tmp_path / "curated", tmp_path / "report"
    summary = curate(profile, policy, output, report)
    assert summary["audit_valid"] and summary["kept_images"] == 3
    assert summary["kept_annotations"] == 36
    assert summary["actions"]["reviewed_image_rotation"] == 1
    assert summary["actions"]["zero_area_annotation_removed"] == 3
    assert read_manifest(report / "prepared/manifest.json")["dataset_root"] == str(output)
    assert json.loads((output / "provenance.json").read_text())["policy"]
    assert before == {
        str(p): digest_bytes(p.read_bytes()) for p in profile.root.rglob("*") if p.is_file()
    }
    assert (report / "index.html").is_file()
    assert set(summary["splits"]["counts"]) == set(SPLITS)
    manifest = report / "prepared/manifest.json"
    comparison = compare_manifests(manifest, manifest, report / "comparison-test.json")
    assert comparison["exact_byte_pairs"] == 3
    assert (
        sum(summary[key] for key in ("kept_images", "quarantined_images", "removed_copy_images"))
        == 3
    )
    with pytest.raises(ValueError, match="already exists"):
        curate(profile, policy, output, report)
    with pytest.raises(ValueError, match="already belongs"):
        curate(profile, policy, tmp_path / "new-version", report)


def test_three_capture_groups_can_fill_all_splits():
    rows = [sample_row(str(i), f"day-{i // 3}", f"pixel-{i}") for i in range(9)]
    result = assign_splits(rows, [])
    assert result["counts"] == {"train": 3, "valid": 3, "test": 3}


def test_class_coverage_is_repaired_using_whole_groups():
    rows = [sample_row(str(i), f"day-{i}", f"pixel-{i}") for i in range(12)]
    for row in rows[3:6]:
        row["annotations"] = [{"id": 2, "label": "black-rook", "bbox": [5, 6, 10, 12]}]
    assign_splits(rows, [])
    for split in SPLITS:
        assert {
            a["label"] for row in rows if row["split"] == split for a in row["annotations"]
        } == {"white-rook", "black-rook"}


def test_class_coverage_does_not_break_a_single_independent_group():
    rows = [sample_row(str(i), f"day-{i}", f"pixel-{i}") for i in range(9)]
    rows[0]["annotations"] = [{"id": 2, "label": "black-rook", "bbox": [5, 6, 10, 12]}]
    with pytest.raises(ValueError, match="independent labeled groups"):
        assign_splits(rows, [])


def test_reviewed_snapshot_change_prevents_publication(tmp_path):
    profile, policy = make_source(tmp_path)
    source = next((profile.root / "test").glob("*.png"))
    Image.new("RGB", (64, 48), "red").save(source)
    with pytest.raises(ValueError, match="snapshot differs"):
        curate(profile, policy, tmp_path / "curated", tmp_path / "report")
    assert not (tmp_path / "curated").exists()


def test_output_and_report_cannot_touch_raw_input(tmp_path):
    profile, policy = make_source(tmp_path)
    with pytest.raises(ValueError, match="must not overlap"):
        curate(profile, policy, profile.root / "curated", tmp_path / "report")
    with pytest.raises(ValueError, match="must not overlap"):
        curate(profile, policy, tmp_path / "curated", profile.root / "report")
