"""Publish compact aggregate merge results, never raw photos or candidate weights."""

import argparse
import csv
import json
from pathlib import Path

from .data import save_json


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
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), constrained_layout=True)
    colors = {"deployed": "#6484a2", "control": "#c49b52", "merged": "#2b6cb0"}
    sources = sorted(report["results"]["deployed"]["test"]["per_source"])
    for axis, metric, title in zip(
        axes,
        ("typed_piece_recall", "typed_prediction_precision", "typed_f1"),
        ("Correctly identified / real pieces", "Correctly identified / predictions", "Typed F1"),
        strict=True,
    ):
        for offset, arm in enumerate(colors):
            values = [
                report["results"][arm]["test"]["per_source"][source][metric] * 100
                for source in sources
            ]
            bars = axis.bar(
                np.arange(len(sources)) + (offset - 1) * 0.25,
                values,
                0.24,
                label=arm,
                color=colors[arm],
            )
            axis.bar_label(bars, fmt="%.1f", fontsize=8, padding=3)
        axis.set_xticks(
            range(len(sources)),
            [
                f"{source}\n{report['results']['deployed']['test']['per_source'][source]['images']} images / "
                f"{report['results']['deployed']['test']['per_source'][source]['annotated_pieces']:,} pieces"
                for source in sources
            ],
        )
        axis.set_ylim(0, 108)
        axis.set_title(title, fontsize=11)
        axis.set_ylabel("Percent")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=0.15)
        axis.set_axisbelow(True)
    axes[0].legend(loc="lower left", fontsize=9)
    fig.suptitle("Two-source merge: fixed image holdouts, not whole-board accuracy", fontsize=13)
    fig.savefig(output / "comparison.png", dpi=150)
    plt.close(fig)
    lines = [
        "# Combined-Dataset Results",
        "",
        "Recorded November 8, 2026. See [the preregistered protocol](PROTOCOL.md) for selection rules and limitations.",
        "",
        "![Source-specific recognition comparison](comparison.png)",
        "",
        "| Model | Source | Correct / real pieces | Correct / predictions | Typed F1 | Missed | Extra |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['source']} | {row['typed_piece_recall']:.2%} | {row['typed_prediction_precision']:.2%} | {row['typed_f1']:.2%} | {row['missed_pieces']} | {row['unmatched_predictions']} |"
        )
    lines += ["", "## Primary Comparison", ""]
    for arm in colors:
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
        report["decision"]["next_step"],
        "Deployed models and website metrics are unchanged by this experiment.",
        "",
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
