from PIL import Image

from scanner.ml.data import CocoPieces, prepare_dataset, read_manifest
from scanner.ml.metrics import operating_metrics
from scanner.ml.report import evaluation_report


def test_report_writes_paired_images_and_explains_metric_limits(dataset_root, tmp_path):
    prepare_dataset(dataset_root, tmp_path / "prepared")
    dataset = CocoPieces(read_manifest(tmp_path / "prepared/manifest.json"), "test")
    record = dataset.records[0]
    predictions = [
        {
            "image_id": record["id"],
            "boxes": record["boxes"],
            "labels": record["labels"],
            "scores": [0.9],
        }
    ]
    metrics = {**operating_metrics(predictions, dataset.records, 0.2), "map50": 1}
    output = tmp_path / "report"
    evaluation_report(output, dataset.root, dataset.records, predictions, metrics)
    assert "not 64-square board accuracy" in (output / "index.html").read_text()
    with Image.open(output / f"image-{record['id']}.jpg") as image:
        assert image.size == (128, 48)
