"""Export versioned pipeline comparisons and corrected-label sensitivity reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from .benchmark import piece_diagnostics
from .data import read_manifest, save_json
from .piece_errors import analyze, write_csv


def export(experiment, manifest_path, reviewed_path, baseline, training, output, recorded_on):
    if output.exists():
        raise ValueError("Use a new report directory; previous benchmarks are immutable.")
    result = json.loads((experiment / "results.json").read_text())
    manifest, reviewed = read_manifest(manifest_path), read_manifest(reviewed_path)
    if result["dataset_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("Experiment and source manifest differ.")
    if reviewed.get("parent_fingerprint") != manifest["fingerprint"]:
        raise ValueError("Reviewed labels are not a direct version of the source manifest.")
    if result["selected_pipeline"] != "combined":
        raise ValueError("This report expects the combined pipeline to have passed validation.")
    output.mkdir(parents=True)
    result.update(
        {
            "recorded_on": recorded_on.isoformat(),
            "run_id": "chess-v2-v3-crops-v1",
            "training": json.loads((training / "training.json").read_text()),
            "config": json.loads((training / "config.json").read_text()),
            "runtime": json.loads((experiment / "runtime.json").read_text()),
            "limitations": [
                "Box-level diagnostics, not square or full-board accuracy.",
                "Test errors had previously been inspected; this is a development benchmark, not a pristine new holdout.",
                "Limited physical-set diversity; new unseen sets still required.",
            ],
        }
    )
    rows, corrected, detail = [], {}, {}
    for split, directory in (("valid", "validation"), ("test", "test")):
        records = [r for r in manifest["records"] if r["split"] == split]
        reviewed_records = [r for r in reviewed["records"] if r["split"] == split]
        original_path = baseline / directory / "predictions.json"
        if (
            hashlib.sha256(original_path.read_bytes()).hexdigest()
            != result["splits"][split]["source_predictions_sha256"]
        ):
            raise ValueError("Frozen detector predictions changed after the experiment.")
        original = json.loads(original_path.read_text())
        selected_path = experiment / f"{split}-combined-predictions.json"
        selected = json.loads(selected_path.read_text())
        checked = piece_diagnostics(selected, records, result["threshold"])
        if checked != result["splits"][split]["variants"]["combined"]:
            raise ValueError("Saved pipeline predictions do not reproduce experiment metrics.")
        detail[split], _ = analyze(selected, records, result["threshold"])
        for key in ("by_actual_class", "by_actual_type", "by_predicted_class", "confusions"):
            write_csv(output / f"{split}-{key}.csv", detail[split][key])
        corrected[split] = {
            "baseline": piece_diagnostics(original, reviewed_records, result["threshold"]),
            "combined": piece_diagnostics(selected, reviewed_records, result["threshold"]),
        }
        for version, variants in (
            ("v3", result["splits"][split]["variants"]),
            ("v4-reviewed", corrected[split]),
        ):
            for name, metrics in variants.items():
                rows.append(
                    {
                        "recorded_on": recorded_on.isoformat(),
                        "labels": version,
                        "pipeline": name,
                        "split": split,
                        **{
                            key: value
                            for key, value in metrics.items()
                            if not isinstance(value, (dict, list))
                        },
                    }
                )
        result["splits"][split]["combined_predictions_sha256"] = hashlib.sha256(
            selected_path.read_bytes()
        ).hexdigest()
    result["corrected_labels"] = {
        "fingerprint": reviewed["fingerprint"],
        "note": "Two added test annotations only; same frozen predictions, no model/threshold changes.",
        "splits": corrected,
    }
    result["piece_errors"] = detail
    save_json(output / "results.json", result)
    write_csv(output / "metrics.csv", rows)
    save_json(output / "training-history.json", json.loads((training / "history.json").read_text()))
    print(f"Exported immutable metrics and piece diagnostics to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("experiment", "manifest", "reviewed", "baseline", "training", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--recorded-on", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    export(
        args.experiment,
        args.manifest,
        args.reviewed,
        args.baseline,
        args.training,
        args.output,
        args.recorded_on,
    )
