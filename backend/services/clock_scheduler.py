from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from backend.repositories import GameRecord

ClockDeadlineRunner = Callable[[GameRecord], Awaitable[None]]


class ClockDeadlineScheduler:
    """Keeps one version-bound clock deadline task per active game."""

    def __init__(self, runner: ClockDeadlineRunner) -> None:
        self._runner = runner
        self._tasks: dict[str, tuple[int, asyncio.Task[None]]] = {}

    def schedule(self, record: GameRecord) -> bool:
        game_id = record.state.id
        current = self._tasks.get(game_id)
        if current is not None and not current[1].done():
            if current[0] == record.version:
                return False
            self._cancel_task(current[1])

        task = asyncio.create_task(self._execute(record))
        self._tasks[game_id] = (record.version, task)
        task.add_done_callback(
            lambda completed, target=game_id, version=record.version: self._discard(
                target,
                version,
                completed,
            )
        )
        return True

    async def _execute(self, record: GameRecord) -> None:
        await self._runner(record)

    def _discard(
        self,
        game_id: str,
        expected_version: int,
        task: asyncio.Task[None],
    ) -> None:
        current = self._tasks.get(game_id)
        if current == (expected_version, task):
            self._tasks.pop(game_id, None)

    @staticmethod
    def _cancel_task(task: asyncio.Task[None]) -> None:
        if task is not asyncio.current_task() and not task.done():
            task.cancel()

    def cancel(self, game_id: str) -> None:
        current = self._tasks.pop(game_id, None)
        if current is not None:
            self._cancel_task(current[1])

    def is_scheduled(self, game_id: str, version: int | None = None) -> bool:
        current = self._tasks.get(game_id)
        if current is None or current[1].done():
            return False
        return version is None or current[0] == version

    async def shutdown(self) -> None:
        tasks = [task for _, task in self._tasks.values()]
        self._tasks.clear()
        for task in tasks:
            self._cancel_task(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
