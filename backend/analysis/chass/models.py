from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.schemas import PositionFactorView


@dataclass(frozen=True)
class ChassEngineResult:
    score: float
    white_share: float
    mate_in: int | None
    factors: tuple[PositionFactorView, ...]
    depth: int
    nodes: int
    elapsed_ms: int
    engine_version: str
    model_version: str
    immediate_winner: str | None = None
    diagnostics: dict[str, float | int | str] = field(default_factory=dict)
