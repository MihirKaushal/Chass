import assert from "node:assert/strict";
import test from "node:test";

import {
  activeClockTiming,
  clockDeadlineDelayMs,
  clockRemainingByColor,
  projectClockAfterTurn,
} from "./gameClock.js";


const CLOCK = {
  initialSeconds: 60,
  remainingSeconds: { white: 60, black: 60 },
  activeColor: "white",
  turnStartedAt: "2026-10-04T12:00:00Z",
};


test("clock timing derives one exact deadline for display, audio, and timeout", () => {
  const now = Date.parse("2026-10-04T12:00:29.250Z");
  const timing = activeClockTiming(CLOCK, now);

  assert.equal(timing.remainingSeconds, 30.75);
  assert.equal(timing.deadlineMs, Date.parse("2026-10-04T12:01:00Z"));
  assert.equal(clockDeadlineDelayMs(CLOCK, now), 30750);
  assert.deepEqual(clockRemainingByColor(CLOCK, now), {
    white: 30.75,
    black: 60,
  });
});


test("projecting a completed turn preserves elapsed time and starts the opponent clock", () => {
  const now = Date.parse("2026-10-04T12:00:04.500Z");
  const projected = projectClockAfterTurn(CLOCK, "black", now);

  assert.equal(projected.remainingSeconds.white, 55.5);
  assert.equal(projected.remainingSeconds.black, 60);
  assert.equal(projected.activeColor, "black");
  assert.equal(projected.turnStartedAt, "2026-10-04T12:00:04.500Z");
  assert.equal(CLOCK.remainingSeconds.white, 60);
});
