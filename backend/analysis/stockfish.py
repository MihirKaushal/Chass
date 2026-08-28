from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineAnalysis:
    centipawns: int | None
    mate_in: int | None
    win: int | None
    draw: int | None
    loss: int | None
    depth: int | None
    nodes: int | None
    principal_variation: list[str] = field(default_factory=list)
    elapsed_ms: int = 0
    engine_version: str = "Stockfish"


@dataclass(frozen=True)
class EngineMoveCandidate:
    move: str
    centipawns: int | None
    mate_in: int | None
    depth: int | None
    nodes: int | None


@dataclass(frozen=True)
class EngineMoveSearch:
    best_move: str | None
    candidates: list[EngineMoveCandidate] = field(default_factory=list)
    elapsed_ms: int = 0
    engine_version: str = "Stockfish"


def parse_uci_info(line: str) -> dict[str, object]:
    tokens = line.split()
    parsed: dict[str, object] = {}

    def integer_after(name: str, offset: int = 1) -> int | None:
        try:
            return int(tokens[tokens.index(name) + offset])
        except (ValueError, IndexError):
            return None

    parsed["depth"] = integer_after("depth")
    parsed["nodes"] = integer_after("nodes")
    multipv = integer_after("multipv")
    if multipv is not None:
        parsed["multipv"] = multipv

    try:
        score_index = tokens.index("score")
        score_kind = tokens[score_index + 1]
        score_value = int(tokens[score_index + 2])
        if score_kind == "cp":
            parsed["centipawns"] = score_value
            parsed["mate_in"] = None
        elif score_kind == "mate":
            parsed["centipawns"] = None
            parsed["mate_in"] = score_value
    except (ValueError, IndexError):
        pass

    try:
        wdl_index = tokens.index("wdl")
        parsed["win"] = int(tokens[wdl_index + 1])
        parsed["draw"] = int(tokens[wdl_index + 2])
        parsed["loss"] = int(tokens[wdl_index + 3])
    except (ValueError, IndexError):
        pass

    try:
        pv_index = tokens.index("pv")
        parsed["principal_variation"] = tokens[pv_index + 1 :]
    except ValueError:
        pass
    return parsed


class StockfishUciProvider:
    def __init__(
        self,
        *,
        configured_path: str,
        enabled: bool = True,
        movetime_ms: int = 180,
        hash_mb: int = 32,
        threads: int = 1,
        startup_timeout_seconds: int = 15,
        startup_attempts: int = 2,
        engine_label: str = "Stockfish",
        binary_names: tuple[str, ...] = ("stockfish",),
    ) -> None:
        self.enabled = enabled
        self.configured_path = configured_path
        self.movetime_ms = max(25, movetime_ms)
        self.hash_mb = max(1, hash_mb)
        self.threads = max(1, threads)
        self.startup_timeout_seconds = max(1, startup_timeout_seconds)
        self.startup_attempts = max(1, startup_attempts)
        self.engine_label = engine_label
        self.binary_names = binary_names
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._engine_name = engine_label
        self._last_error: str | None = None
        self._public_error: str | None = None
        self._resolved_path: str | None = None

    @property
    def engine_name(self) -> str:
        return self._engine_name

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def public_error(self) -> str | None:
        return self._public_error

    @property
    def ready(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def _resolve_path(self) -> str | None:
        candidates: list[str | None] = [
            self.configured_path,
            *(shutil.which(name) for name in self.binary_names),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            expanded = str(Path(candidate).expanduser())
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                return expanded
        return None

    async def _write(self, command: str) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError(f"{self.engine_label} is not running")
        self._process.stdin.write(f"{command}\n".encode("ascii"))
        await self._process.stdin.drain()

    async def _readline(self) -> str:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError(f"{self.engine_label} is not running")
        raw = await self._process.stdout.readline()
        if not raw:
            raise RuntimeError(f"{self.engine_label} exited unexpectedly")
        return raw.decode("utf-8", errors="replace").strip()

    async def _read_until(self, expected: str) -> list[str]:
        lines: list[str] = []
        while True:
            line = await self._readline()
            lines.append(line)
            if line == expected or line.startswith(f"{expected} "):
                return lines

    async def _start_locked(self) -> bool:
        if not self.enabled:
            self._last_error = f"The {self.engine_label} engine is disabled on this server."
            self._public_error = "Live analysis is disabled on this server."
            return False
        if self.ready:
            self._public_error = None
            return True

        path = self._resolve_path()
        if path is None:
            self._last_error = (
                f"{self.engine_label} is not installed on this server. "
                "The game remains fully playable."
            )
            self._public_error = "The analysis engine is not installed on this server."
            return False

        for attempt in range(1, self.startup_attempts + 1):
            try:
                self._process = await asyncio.create_subprocess_exec(
                    path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._resolved_path = path
                await self._write("uci")
                handshake = await asyncio.wait_for(
                    self._read_until("uciok"),
                    timeout=self.startup_timeout_seconds,
                )
                for line in handshake:
                    if line.startswith("id name "):
                        self._engine_name = line.removeprefix("id name ").strip()
                await self._write(f"setoption name Threads value {self.threads}")
                await self._write(f"setoption name Hash value {self.hash_mb}")
                await self._write("setoption name MultiPV value 1")
                await self._write("setoption name UCI_ShowWDL value true")
                await self._write("isready")
                await asyncio.wait_for(
                    self._read_until("readyok"),
                    timeout=self.startup_timeout_seconds,
                )
                self._last_error = None
                self._public_error = None
                logger.info("Match Analysis ready with %s", self._engine_name)
                return True
            except asyncio.CancelledError:
                await self._terminate_locked()
                raise
            except Exception as error:
                detail = f"{type(error).__name__}: {error}".rstrip()
                self._last_error = (
                    f"{self.engine_label} startup attempt {attempt}/{self.startup_attempts} "
                    f"failed: {detail}"
                )
                self._public_error = (
                    "The analysis engine is still warming up or could not start. Retry in a moment."
                )
                logger.warning(self._last_error)
                await self._terminate_locked()
                if attempt < self.startup_attempts:
                    await asyncio.sleep(0.5 * attempt)
        return False

    async def start(self) -> bool:
        async with self._lock:
            return await self._start_locked()

    async def _terminate_locked(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                return
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    return
                await process.wait()

    async def close(self) -> None:
        async with self._lock:
            if self.ready:
                try:
                    await self._write("quit")
                    await asyncio.wait_for(self._process.wait(), timeout=1)
                    self._process = None
                    return
                except Exception:
                    pass
            await self._terminate_locked()

    async def _search_locked(self, fen: str) -> EngineAnalysis:
        started = perf_counter()
        latest: dict[str, object] = {}
        try:
            await self._set_search_options_locked(multipv=1, limit_strength_elo=None)
            await self._write(f"position fen {fen}")
            await self._write(f"go movetime {self.movetime_ms}")
            timeout_seconds = max(2.0, (self.movetime_ms / 1000) + 2.0)

            async def read_search() -> None:
                nonlocal latest
                while True:
                    line = await self._readline()
                    if line.startswith("info "):
                        parsed = parse_uci_info(line)
                        if "centipawns" in parsed or "mate_in" in parsed:
                            latest.pop("centipawns", None)
                            latest.pop("mate_in", None)
                        latest = {
                            **latest,
                            **{key: value for key, value in parsed.items() if value is not None},
                        }
                    elif line.startswith("bestmove"):
                        return

            await asyncio.wait_for(read_search(), timeout=timeout_seconds)
        except asyncio.CancelledError:
            await self._terminate_locked()
            raise
        except Exception as error:
            self._last_error = (
                f"{self.engine_label} analysis failed: {type(error).__name__}: {error}"
            ).rstrip()
            self._public_error = "The analysis engine stopped unexpectedly. Retry in a moment."
            await self._terminate_locked()
            raise

        elapsed_ms = round((perf_counter() - started) * 1000)
        if "centipawns" not in latest and "mate_in" not in latest:
            self._last_error = f"{self.engine_label} returned no position evaluation"
            self._public_error = (
                "The analysis engine did not return a position estimate. Retry in a moment."
            )
            await self._terminate_locked()
            raise RuntimeError(f"{self.engine_label} returned no position evaluation")
        return EngineAnalysis(
            centipawns=latest.get("centipawns"),
            mate_in=latest.get("mate_in"),
            win=latest.get("win"),
            draw=latest.get("draw"),
            loss=latest.get("loss"),
            depth=latest.get("depth"),
            nodes=latest.get("nodes"),
            principal_variation=list(latest.get("principal_variation", [])),
            elapsed_ms=elapsed_ms,
            engine_version=self._engine_name,
        )

    async def _set_search_options_locked(
        self,
        *,
        multipv: int,
        limit_strength_elo: int | None,
    ) -> None:
        await self._write(f"setoption name MultiPV value {max(1, multipv)}")
        if limit_strength_elo is None:
            await self._write("setoption name UCI_LimitStrength value false")
            await self._write("setoption name Skill Level value 20")
        else:
            await self._write("setoption name UCI_LimitStrength value true")
            await self._write(f"setoption name UCI_Elo value {limit_strength_elo}")
        await self._write("isready")
        await asyncio.wait_for(
            self._read_until("readyok"),
            timeout=self.startup_timeout_seconds,
        )

    async def _search_moves_locked(
        self,
        fen: str,
        *,
        search_moves: list[str],
        multipv: int,
        nodes: int | None,
        movetime_ms: int | None,
        limit_strength_elo: int | None,
    ) -> EngineMoveSearch:
        if not search_moves:
            raise ValueError("At least one legal move is required for an engine search.")
        if nodes is not None and movetime_ms is not None:
            raise ValueError("Choose either a node limit or a time limit, not both.")

        started = perf_counter()
        latest_by_rank: dict[int, dict[str, object]] = {}
        best_move: str | None = None
        candidate_count = min(max(1, multipv), len(search_moves))
        try:
            await self._set_search_options_locked(
                multipv=candidate_count,
                limit_strength_elo=limit_strength_elo,
            )
            await self._write(f"position fen {fen}")
            if nodes is not None:
                command = f"go nodes {max(1, nodes)}"
                timeout_seconds = max(3.0, min(15.0, nodes / 25_000 + 3.0))
            else:
                search_time = max(25, movetime_ms or self.movetime_ms)
                command = f"go movetime {search_time}"
                timeout_seconds = max(2.0, (search_time / 1_000) + 2.0)
            command = f"{command} searchmoves {' '.join(search_moves)}"
            await self._write(command)

            async def read_search() -> None:
                nonlocal best_move
                while True:
                    line = await self._readline()
                    if line.startswith("info "):
                        parsed = parse_uci_info(line)
                        variation = list(parsed.get("principal_variation", []))
                        if not variation:
                            continue
                        rank = int(parsed.get("multipv", 1))
                        current = latest_by_rank.get(rank, {})
                        if "centipawns" in parsed or "mate_in" in parsed:
                            current.pop("centipawns", None)
                            current.pop("mate_in", None)
                        latest_by_rank[rank] = {
                            **current,
                            **{key: value for key, value in parsed.items() if value is not None},
                        }
                    elif line.startswith("bestmove"):
                        tokens = line.split()
                        if len(tokens) > 1 and tokens[1] not in {"(none)", "0000"}:
                            best_move = tokens[1]
                        return

            await asyncio.wait_for(read_search(), timeout=timeout_seconds)
        except asyncio.CancelledError:
            await self._terminate_locked()
            raise
        except Exception as error:
            self._last_error = (
                f"{self.engine_label} move search failed: {type(error).__name__}: {error}"
            ).rstrip()
            self._public_error = "The chess engine stopped unexpectedly. Retry in a moment."
            await self._terminate_locked()
            raise

        candidates: list[EngineMoveCandidate] = []
        for rank in sorted(latest_by_rank):
            values = latest_by_rank[rank]
            variation = list(values.get("principal_variation", []))
            if not variation:
                continue
            candidates.append(
                EngineMoveCandidate(
                    move=variation[0],
                    centipawns=values.get("centipawns"),
                    mate_in=values.get("mate_in"),
                    depth=values.get("depth"),
                    nodes=values.get("nodes"),
                )
            )

        if best_move is None and candidates:
            best_move = candidates[0].move
        if best_move is None:
            self._last_error = f"{self.engine_label} returned no legal bot move"
            self._public_error = "The chess engine did not return a move. Retry in a moment."
            raise RuntimeError(self._last_error)

        return EngineMoveSearch(
            best_move=best_move,
            candidates=candidates,
            elapsed_ms=round((perf_counter() - started) * 1_000),
            engine_version=self._engine_name,
        )

    async def analyze(self, fen: str) -> EngineAnalysis:
        async with self._lock:
            if not await self._start_locked():
                raise RuntimeError(self._last_error or f"{self.engine_label} is unavailable")
            return await self._search_locked(fen)

    async def search_moves(
        self,
        fen: str,
        *,
        search_moves: list[str],
        multipv: int = 1,
        nodes: int | None = None,
        movetime_ms: int | None = None,
        limit_strength_elo: int | None = None,
    ) -> EngineMoveSearch:
        async with self._lock:
            if not await self._start_locked():
                raise RuntimeError(self._last_error or f"{self.engine_label} is unavailable")
            return await self._search_moves_locked(
                fen,
                search_moves=search_moves,
                multipv=multipv,
                nodes=nodes,
                movetime_ms=movetime_ms,
                limit_strength_elo=limit_strength_elo,
            )
