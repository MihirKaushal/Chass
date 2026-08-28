from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

BotTurnRunner = Callable[[str, int], Awaitable[None]]


class BotTurnScheduler:
    """Keeps at most one recoverable bot task active for each game."""

    def __init__(self, runner: BotTurnRunner) -> None:
        self._runner = runner
        self._tasks: dict[str, tuple[int, asyncio.Task[None]]] = {}

    def schedule(self, game_id: str, expected_version: int) -> bool:
        current = self._tasks.get(game_id)
        if current is not None and not current[1].done():
            if current[0] == expected_version:
                return False
            current[1].cancel()

        task = asyncio.create_task(self._execute(game_id, expected_version))
        self._tasks[game_id] = (expected_version, task)
        task.add_done_callback(
            lambda completed, target=game_id, version=expected_version: self._discard(
                target,
                version,
                completed,
            )
        )
        return True

    async def _execute(self, game_id: str, expected_version: int) -> None:
        await self._runner(game_id, expected_version)

    def _discard(
        self,
        game_id: str,
        expected_version: int,
        task: asyncio.Task[None],
    ) -> None:
        current = self._tasks.get(game_id)
        if current == (expected_version, task):
            self._tasks.pop(game_id, None)

    def cancel(self, game_id: str) -> None:
        current = self._tasks.pop(game_id, None)
        if current is not None and not current[1].done():
            current[1].cancel()

    def is_scheduled(self, game_id: str, version: int | None = None) -> bool:
        current = self._tasks.get(game_id)
        if current is None or current[1].done():
            return False
        return version is None or current[0] == version

    async def shutdown(self) -> None:
        tasks = [task for _, task in self._tasks.values()]
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
