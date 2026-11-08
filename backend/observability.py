"""Bounded process-local operational aggregates, with no user or image identifiers."""

from collections import Counter
from threading import Lock
from time import perf_counter


class OperationalMetrics:
    def __init__(self):
        self._lock = Lock()
        self._started = perf_counter()
        self._counts = Counter()
        self._durations = {}

    def record(self, operation: str, outcome: str, elapsed_ms: float = 0):
        if operation not in {"analysis", "scanner", "import", "engine_fallback"}:
            raise ValueError("Unknown metric operation")
        if outcome not in {"ok", "error", "cancelled", "stockfish", "fairy-stockfish", "chass"}:
            raise ValueError("Unknown metric outcome")
        with self._lock:
            self._counts[f"{operation}.{outcome}"] += 1
            count, total, maximum = self._durations.get(operation, (0, 0, 0))
            duration = max(0, elapsed_ms)
            self._durations[operation] = (count + 1, total + duration, max(maximum, duration))

    def snapshot(self):
        with self._lock:
            return {
                "scope": "process_lifetime",
                "uptimeSeconds": round(perf_counter() - self._started),
                "counts": dict(self._counts),
                "latencyMs": {
                    name: {
                        "count": count,
                        "mean": round(total / count, 2),
                        "max": round(maximum, 2),
                    }
                    for name, (count, total, maximum) in self._durations.items()
                },
            }


metrics = OperationalMetrics()
