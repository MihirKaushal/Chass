import json
import subprocess
import sys

from scanner.ml.data import CLASSES, prepare_dataset, read_manifest
from scanner.ml.datasets import CHESS_V2, TOP_DOWN, prepared_directory

from .conftest import change_annotations


def test_chess_v2_aliases_and_attribution(dataset_root, tmp_path):
    for split in ("train", "valid", "test"):

        def change(data):
            data["categories"][0]["name"] = "Chess"
            data["categories"][1]["name"] = "WR"

        change_annotations(dataset_root, change, split)
    output = tmp_path / "v2"
    audit = prepare_dataset(dataset_root, output, profile=CHESS_V2)
    manifest = read_manifest(output / "manifest.json")
    assert audit["dataset"] == "chess-v2"
    assert audit["declared_total_images"] == 3
    assert audit["declared_total_annotations"] == 3
    assert manifest["source"] == CHESS_V2.source
    assert manifest["category_aliases"]["WR"] == "white-rook"
    assert manifest["records"][0]["labels"] == [CLASSES.index("white-rook")]
    assert "416x416" not in " ".join(audit["limitations"])
    assert set(CHESS_V2.category_aliases.values()) == set(CLASSES[1:])


def test_profiles_do_not_overwrite_each_other():
    assert TOP_DOWN.root.name == "ChessTopDown.v2-chess2.coco"
    assert CHESS_V2.root.name == "ChessV2.v1i.coco"
    assert prepared_directory(TOP_DOWN) != prepared_directory(CHESS_V2)


def test_cli_selects_v2_profile(dataset_root, tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scanner.ml",
            "prepare",
            "--dataset",
            "chess-v2",
            "--data",
            str(dataset_root),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    # Canonical labels are also accepted; the fixture has Top Down's supercategory.
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "audit failed" in result.stderr
    assert not (output / "manifest.json").exists()
    for split in ("train", "valid", "test"):
        change_annotations(
            dataset_root, lambda data: data["categories"][0].update(name="Chess"), split
        )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scanner.ml",
            "prepare",
            "--dataset",
            "chess-v2",
            "--data",
            str(dataset_root),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["dataset"] == "chess-v2"
