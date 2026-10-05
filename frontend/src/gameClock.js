export const CLOCK_RENDER_INTERVAL_MS = 100;


export function activeClockTiming(clock, nowMs = Date.now()) {
  if (!clock) return null;

  const activeColor = clock.activeColor;
  const storedRemaining = Number(clock.remainingSeconds?.[activeColor]);
  const turnStartedAtMs = new Date(clock.turnStartedAt).getTime();
  if (
    !["white", "black"].includes(activeColor)
    || !Number.isFinite(storedRemaining)
    || !Number.isFinite(turnStartedAtMs)
  ) {
    return null;
  }

  const elapsedSeconds = Math.max(0, (nowMs - turnStartedAtMs) / 1000);
  const remainingSeconds = Math.max(0, storedRemaining - elapsedSeconds);
  return {
    activeColor,
    remainingSeconds,
    deadlineMs: nowMs + remainingSeconds * 1000,
  };
}


export function clockRemainingByColor(clock, nowMs = Date.now()) {
  if (!clock) return null;
  const timing = activeClockTiming(clock, nowMs);
  if (!timing) return null;

  return {
    ...clock.remainingSeconds,
    [timing.activeColor]: timing.remainingSeconds,
  };
}


export function clockDeadlineDelayMs(clock, nowMs = Date.now()) {
  const timing = activeClockTiming(clock, nowMs);
  return timing ? Math.max(0, timing.deadlineMs - nowMs) : null;
}


export function projectClockAfterTurn(clock, nextColor, nowMs = Date.now()) {
  if (!clock || !["white", "black"].includes(nextColor)) return clock;
  const remainingSeconds = clockRemainingByColor(clock, nowMs);
  if (!remainingSeconds) return clock;

  return {
    ...clock,
    remainingSeconds,
    activeColor: nextColor,
    turnStartedAt: new Date(nowMs).toISOString(),
  };
}
