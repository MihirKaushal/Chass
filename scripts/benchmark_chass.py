"""Repeatable native-engine measurements. Search exhaustion is not a failed request."""

import argparse
import json
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.analysis.chass import ChassAnalysisProvider  # noqa: E402
from backend.rules import RuleEngine  # noqa: E402
from scripts.verification_positions import benchmark_positions  # noqa: E402


def benchmark(repeats=3, budget_ms=180):
    provider = ChassAnalysisProvider(RuleEngine(), movetime_ms=budget_ms)
    cases = {}
    for name, state in benchmark_positions().items():
        runs = [provider._analyze_sync(state.clone()) for _ in range(repeats)]
        cases[name] = {
            "meanMs": round(statistics.mean(result.elapsed_ms for result in runs), 2),
            "maxMs": max(result.elapsed_ms for result in runs),
            "budgetExhaustionRate": sum(
                bool(result.diagnostics["budgetExhausted"]) for result in runs
            )
            / repeats,
            "runs": [
                {
                    "elapsedMs": result.elapsed_ms,
                    "depth": result.depth,
                    "nodes": result.nodes,
                    "budgetExhausted": result.diagnostics["budgetExhausted"],
                }
                for result in runs
            ],
        }
    return {
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "engine": provider.engine_name,
        "repeats": repeats,
        "searchBudgetMs": budget_ms,
        "note": "Wall-clock evaluation time includes legal-action preparation outside the search budget. Not a network benchmark or an Elo calibration.",
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--budget-ms", type=int, default=180)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100 or not 25 <= args.budget_ms <= 2000:
        parser.error("Use 1-100 repeats and a 25-2000 ms search budget")
    output = json.dumps(benchmark(args.repeats, args.budget_ms), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output, end="")
