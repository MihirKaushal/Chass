from __future__ import annotations

import asyncio
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.analysis.profiles import AnalysisProfile
from backend.analysis.stockfish import (
    EngineAnalysis,
    EngineMoveSearch,
    StockfishUciProvider,
    parse_uci_info,
)

_MOVE_PATTERN = re.compile(r"^([a-l])(10|[1-9])([a-l])(10|[1-9])(?:[a-z])?:\s+\d+$")


@dataclass(frozen=True)
class FairyPositionInspection:
    legal_moves: frozenset[tuple[int, int, int, int]]
    terminal_outcome: str | None


def parse_fairy_perft_move(
    line: str,
    *,
    rows: int,
    cols: int,
) -> tuple[int, int, int, int] | None:
    match = _MOVE_PATTERN.match(line.strip())
    if match is None:
        return None
    from_col = ord(match.group(1)) - ord("a")
    from_row = rows - int(match.group(2))
    to_col = ord(match.group(3)) - ord("a")
    to_row = rows - int(match.group(4))
    if not (
        0 <= from_row < rows and 0 <= from_col < cols and 0 <= to_row < rows and 0 <= to_col < cols
    ):
        return None
    return from_row, from_col, to_row, to_col


class FairyStockfishUciProvider(StockfishUciProvider):
    def __init__(self, *, max_loaded_profiles: int = 256, **kwargs) -> None:
        super().__init__(
            engine_label="Fairy-Stockfish",
            binary_names=("fairy-stockfish", "fairy-stockfish-largeboard"),
            **kwargs,
        )
        self.max_loaded_profiles = max(1, max_loaded_profiles)
        self._loaded_profiles: dict[str, str] = {}
        self._current_variant: str | None = None
        self._initialized_process: asyncio.subprocess.Process | None = None
        self._registry_path = Path(tempfile.gettempdir()) / (
            f"chass-fairy-variants-{os.getpid()}.ini"
        )

    async def _start_locked(self) -> bool:
        started = await super()._start_locked()
        if not started:
            return False
        if self._initialized_process is self._process:
            return True
        await self._write("setoption name UCI_AnalyseMode value true")
        await self._write("setoption name Use NNUE value false")
        await self._write("setoption name UCI_ShowWDL value true")
        if self._loaded_profiles:
            self._write_registry()
            await self._write(f"setoption name VariantPath value {self._registry_path}")
        await self._write("isready")
        await asyncio.wait_for(
            self._read_until("readyok"),
            timeout=self.startup_timeout_seconds,
        )
        self._initialized_process = self._process
        self._current_variant = None
        return True

    async def _terminate_locked(self) -> None:
        await super()._terminate_locked()
        self._initialized_process = None
        self._current_variant = None

    def _write_registry(self) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "\n".join(
                self._loaded_profiles[profile_id].rstrip()
                for profile_id in sorted(self._loaded_profiles)
            )
            + "\n"
        )
        self._registry_path.write_text(content, encoding="ascii")

    async def _ensure_profile_locked(self, profile: AnalysisProfile) -> None:
        if not profile.variant_name or not profile.variant_definition:
            raise ValueError("Fairy analysis requires a generated variant profile")
        existing = self._loaded_profiles.get(profile.profile_id)
        if existing is not None and existing != profile.variant_definition:
            raise ValueError("Generated Fairy profile ID does not match its definition")
        if existing is None:
            if len(self._loaded_profiles) >= self.max_loaded_profiles:
                await self._terminate_locked()
                self._loaded_profiles.clear()
                if not await self._start_locked():
                    raise RuntimeError(self.last_error or "Fairy-Stockfish is unavailable")
            self._loaded_profiles[profile.profile_id] = profile.variant_definition
            self._write_registry()
            await self._write(f"setoption name VariantPath value {self._registry_path}")
            await self._write("isready")
            await asyncio.wait_for(
                self._read_until("readyok"),
                timeout=self.startup_timeout_seconds,
            )
        if self._current_variant != profile.variant_name:
            await self._write(f"setoption name UCI_Variant value {profile.variant_name}")
            await self._write("isready")
            await asyncio.wait_for(
                self._read_until("readyok"),
                timeout=self.startup_timeout_seconds,
            )
            self._current_variant = profile.variant_name

    async def analyze(self, fen: str, profile: AnalysisProfile) -> EngineAnalysis:
        async with self._lock:
            if not await self._start_locked():
                raise RuntimeError(self.last_error or "Fairy-Stockfish is unavailable")
            await self._ensure_profile_locked(profile)
            return await self._search_locked(fen)

    async def search_moves(
        self,
        fen: str,
        profile: AnalysisProfile,
        *,
        search_moves: list[str],
        multipv: int = 1,
        nodes: int | None = None,
        movetime_ms: int | None = None,
        limit_strength_elo: int | None = None,
    ) -> EngineMoveSearch:
        async with self._lock:
            if not await self._start_locked():
                raise RuntimeError(self.last_error or "Fairy-Stockfish is unavailable")
            await self._ensure_profile_locked(profile)
            return await self._search_moves_locked(
                fen,
                search_moves=search_moves,
                multipv=multipv,
                nodes=nodes,
                movetime_ms=movetime_ms,
                limit_strength_elo=limit_strength_elo,
            )

    async def _terminal_outcome_locked(self, fen: str, side_to_move: str) -> str | None:
        await self._write(f"position fen {fen}")
        await self._write("go depth 1")
        latest: dict[str, object] = {}
        bestmove = ""
        while True:
            line = await self._readline()
            if line.startswith("info "):
                parsed = parse_uci_info(line)
                latest.update({key: value for key, value in parsed.items() if value is not None})
            elif line.startswith("bestmove"):
                bestmove = line.split(maxsplit=1)[1] if " " in line else ""
                break
        if bestmove not in {"(none)", "0000"}:
            return None
        mate_in = latest.get("mate_in")
        if mate_in is None:
            return "draw"
        if int(mate_in) > 0:
            return side_to_move
        return "black" if side_to_move == "white" else "white"

    async def inspect_position(
        self,
        fen: str,
        profile: AnalysisProfile,
        *,
        rows: int,
        cols: int,
        side_to_move: str,
        probe_terminal: bool = False,
    ) -> FairyPositionInspection:
        async with self._lock:
            if not await self._start_locked():
                raise RuntimeError(self.last_error or "Fairy-Stockfish is unavailable")
            await self._ensure_profile_locked(profile)
            try:
                await self._write(f"position fen {fen}")
                await self._write("go perft 1")
                moves: set[tuple[int, int, int, int]] = set()
                while True:
                    line = await asyncio.wait_for(self._readline(), timeout=3)
                    parsed_move = parse_fairy_perft_move(line, rows=rows, cols=cols)
                    if parsed_move is not None:
                        moves.add(parsed_move)
                    if line.startswith("Nodes searched:"):
                        break
                terminal_outcome = None
                if probe_terminal or not moves:
                    terminal_outcome = await asyncio.wait_for(
                        self._terminal_outcome_locked(fen, side_to_move),
                        timeout=3,
                    )
                return FairyPositionInspection(
                    legal_moves=frozenset(moves),
                    terminal_outcome=terminal_outcome,
                )
            except asyncio.CancelledError:
                await self._terminate_locked()
                raise
            except Exception:
                await self._terminate_locked()
                raise
