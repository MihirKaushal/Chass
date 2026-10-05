from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.services import ClockDeadlineScheduler


def test_clock_scheduler_replaces_stale_game_versions() -> None:
    async def scenario() -> None:
        completed: list[int] = []

        async def runner(record) -> None:
            await asyncio.sleep(0.05 if record.version == 1 else 0.001)
            completed.append(record.version)

        scheduler = ClockDeadlineScheduler(runner)
        first = SimpleNamespace(state=SimpleNamespace(id="timed-game"), version=1)
        second = SimpleNamespace(state=SimpleNamespace(id="timed-game"), version=2)

        assert scheduler.schedule(first) is True
        assert scheduler.schedule(first) is False
        assert scheduler.schedule(second) is True
        await asyncio.sleep(0.02)

        assert completed == [2]
        assert scheduler.is_scheduled("timed-game") is False
        await scheduler.shutdown()

    asyncio.run(scenario())
