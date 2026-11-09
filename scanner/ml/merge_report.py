"""Publish compact aggregate merge results, never raw photos or candidate weights."""

import argparse
import csv
import json
from html import escape
from pathlib import Path

from .data import save_json


def chart(report, output):
    colors = {"deployed": "#6484a2", "control": "#c49b52", "merged": "#2b6cb0"}
    sources = sorted(report["results"]["deployed"]["test"]["per_source"])
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 430" role="img">',
        "<title>Source-specific scanner comparison</title>",
        "<desc>Box-level regression metrics for deployed, control, and merged models. Not whole-board accuracy.</desc>",
        '<rect width="1280" height="430" fill="#fff"/>',
        '<g font-family="sans-serif" fill="#1a365d">',
    ]

    def text(x, y, value, size=13, anchor="middle"):
        parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">{escape(str(value))}</text>'
        )

    text(640, 28, "Two-source merge: fixed image holdouts, not whole-board accuracy", 20)
    for index, (arm, color) in enumerate(colors.items()):
        x = 450 + index * 145
        parts.append(f'<rect x="{x}" y="46" width="14" height="14" fill="{color}"/>')
        text(x + 22, 58, arm, anchor="start")
    for panel, (metric, title) in enumerate(
        zip(
            ("typed_piece_recall", "typed_prediction_precision", "typed_f1"),
            (
                "Correctly identified / real pieces",
                "Correctly identified / predictions",
                "Typed F1",
            ),
            strict=True,
        )
    ):
        left = 55 + panel * 420
        text(left + 170, 99, title, 15)
        for tick in (0, 25, 50, 75, 100):
            y = 340 - tick * 2.1
            parts.append(f'<path d="M{left} {y}h340" stroke="#dce3ea"/>')
            text(left - 8, y + 4, f"{tick}%", 11, "end")
        for source_index, source in enumerate(sources):
            center = left + (source_index + 0.5) * 340 / len(sources)
            for offset, (arm, color) in enumerate(colors.items()):
                value = report["results"][arm]["test"]["per_source"][source][metric]
                height = (value or 0) * 210
                x = center + (offset - 1) * 33 - 14
                parts.append(
                    f'<rect x="{x}" y="{340 - height}" width="28" height="{height}" fill="{color}"/>'
                )
                text(x + 14, 333 - height, f"{value * 100:.1f}" if value is not None else "N/A", 11)
            counts = report["results"]["deployed"]["test"]["per_source"][source]
            text(center, 365, source)
            text(
                center,
                385,
                f"{counts['images']} images / {counts['annotated_pieces']:,} pieces",
                11,
            )
    parts.append("</g></svg>")
    (output / "comparison.svg").write_text("\n".join(parts) + "\n")


def percent(value):
    return f"{value:.2%}" if value is not None else "Not defined"


def verification(evaluation, output):
    lines = []
    parity_path = evaluation / "onnx-parity.json"
    if parity_path.exists():
        parity = json.loads(parity_path.read_text())
        save_json(output / "onnx-parity.json", parity)
        passed = parity["board_and_review_parity"] and parity["top_three_label_parity"]
        lines += [
            "## Post-Selection Runtime Checks",
            "",
            f"ONNX parity passed: **{bool(passed)}** on {parity['images']} validation photos, spread within each source. Board/review decisions and top-three labels were compared against PyTorch CPU inference.",
            f"Maximum score difference: {parity['max_score_difference']:.8f}; maximum box-coordinate difference: {parity['max_box_difference_pixels']:.8f} pixels. This checks export consistency, not independent accuracy.",
            "",
            "Details: [onnx-parity.json](onnx-parity.json).",
            "",
        ]
    runtime_path = evaluation / "runtime" / "summary.json"
    if runtime_path.exists():
        runs = json.loads(runtime_path.read_text())
        for run in runs:
            model_name = Path(run["model"]).name
            detail = json.loads(
                (runtime_path.parent / f"{model_name}-b{run['batch_size']}.json").read_text()
            )
            run["samples"] = detail["samples"]
        save_json(output / "runtime.json", runs)
        lines += [
            "Local CPU runtime (one fresh process per model, batch size one):",
            "",
            "| Model | Photos | Median | p95 | Peak process memory |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for run in runs:
            lines.append(
                f"| `{run['model']}` | {len(run['samples'])} | {run['median_ms']:.1f} ms | {run['p95_ms']:.1f} ms | {run['peak_rss_mib']:.1f} MiB |"
            )
        lines += [
            "",
            "Both models received the same validation photos. These are single-run Mac CPU measurements, not Render cold-start, browser, upload, or end-to-end website latency. Small timing differences are not evidence of a speed improvement. The runtime subset is not the accuracy test benchmark.",
            "",
            "Measurements and sampled image IDs: [runtime.json](runtime.json). Candidate ONNX files remain local; browser and hosted integration checks are required before public promotion.",
            "",
        ]
    return lines


def export(evaluation, training, output):
    report = json.loads((evaluation / "results.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    save_json(output / "results.json", report)
    history = {}
    for arm in ("control", "merged"):
        history[arm] = {}
        for stage in ("detector", "classifier"):
            rows = json.loads((training / arm / stage / "history.json").read_text())
            history[arm][stage] = {
                "config": json.loads((training / arm / f"{stage}-config.json").read_text()),
                "epochs": [
                    {
                        "epoch": r["epoch"],
                        "seconds": r["seconds"],
                        "selection_score": r.get("selection_map50", r.get("selection_macro_f1")),
                    }
                    for r in rows
                ],
            }
    save_json(output / "training.json", history)
    fields = [
        "model",
        "source",
        "images",
        "annotated_pieces",
        "typed_piece_recall",
        "typed_prediction_precision",
        "typed_f1",
        "localization_recall",
        "conditional_type_color_accuracy",
        "missed_pieces",
        "unmatched_predictions",
    ]
    rows = []
    for arm in ("deployed", "control", "merged"):
        for source, metrics in report["results"][arm]["test"]["per_source"].items():
            rows.append(
                {"model": arm, "source": source, **{key: metrics[key] for key in fields[2:]}}
            )
    with (output / "metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    chart(report, output)
    lines = [
        "# Combined-Dataset Results",
        "",
        "Recorded November 8, 2026. See [the preregistered protocol](PROTOCOL.md) for selection rules and limitations.",
        "",
        "![Source-specific recognition comparison](comparison.svg)",
        "",
        "| Model | Source | Correct / real pieces | Correct / predictions | Typed F1 | Missed | Extra |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['source']} | {percent(row['typed_piece_recall'])} | {percent(row['typed_prediction_precision'])} | {percent(row['typed_f1'])} | {row['missed_pieces']} | {row['unmatched_predictions']} |"
        )
    lines += ["", "## Primary Comparison", ""]
    for arm in ("deployed", "control", "merged"):
        result = report["results"][arm]["test"]
        lines.append(
            f"- {arm}: equal-source mean typed F1 **{result['macro_source_typed_f1']:.2%}**; pooled correctly identified / real pieces **{result['combined']['typed_piece_recall']:.2%}**."
        )
    low, high = report["bootstrap"]["macro_typed_f1_delta_95_percentile_interval"]
    lines += [
        "",
        f"Paired source-group bootstrap, merged minus control: **{low * 100:+.2f} to {high * 100:+.2f} percentage points** (95% percentile interval, 2,000 resamples).",
        "Only three Chess V2 test groups and 17 Top Down image groups are available. This interval does not account for multiple training seeds or prove physical-set independence.",
        "",
        "## Decision",
        "",
        f"Accuracy gate passed: **{report['decision']['accuracy_gate_passed']}**.",
        "",
    ]
    lines += [f"- {reason}" for reason in report["decision"]["failures"]]
    lines += [
        "",
        "The accuracy gate is separate from deployment readiness. Completed post-selection checks are recorded below when available.",
        "Deployed models and website metrics are unchanged by this experiment.",
        "",
    ]
    lines += verification(evaluation, output)
    lines += [
        "## Scope",
        "",
        "Both detector and classifier were fine-tuned in both arms from identical existing checkpoints, with equal optimizer-update budgets. This is a single-seed continuation experiment, not a claim that all possible mixed-data training recipes perform similarly.",
        "",
        "These are box-level regression metrics. Different source images provide a limited source-shift check, not independently verified unseen-board generalization. No whole-board or empty-square accuracy is available. Follow-up work requires new physical sets with all 64 squares verified.",
        "",
        "Full class/confusion metrics, model hashes, validation choices and decision gates: [results.json](results.json). Plot-ready values: [metrics.csv](metrics.csv). Training budgets/history: [training.json](training.json).",
    ]
    (output / "README.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.evaluation, args.training, args.output)
