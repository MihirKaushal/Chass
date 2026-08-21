function quantity(value, unit) {
  return `${value} ${unit}${value === 1 ? "" : "s"}`;
}

function positiveInteger(value, fallback) {
  const parsed = Math.trunc(Number(value));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function formatMatchDuration(totalSeconds) {
  let remaining = positiveInteger(totalSeconds, 600);
  const hours = Math.floor(remaining / 3600);
  remaining %= 3600;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const parts = [];

  if (hours) parts.push(quantity(hours, "hour"));
  if (minutes) parts.push(quantity(minutes, "minute"));
  if (seconds || !parts.length) parts.push(quantity(seconds, "second"));
  return parts.join(" ");
}

export function victoryDisplayMetadata(victory = {}) {
  switch (victory.mode) {
    case "timed":
      return [
        { label: "Total Time", value: formatMatchDuration(victory.timeSeconds) },
      ];
    case "point_race": {
      const target = positiveInteger(victory.targetPoints, 21);
      const kingPoints = Math.max(0, Math.trunc(Number(victory.kingPoints) || 0));
      return [
        { label: "Target Score", value: quantity(target, "point") },
        { label: "King Value", value: quantity(kingPoints, "point") },
      ];
    }
    case "royal_score": {
      const kingPoints = Math.max(0, Math.trunc(Number(victory.kingPoints) || 0));
      return [
        { label: "King Value", value: quantity(kingPoints, "point") },
      ];
    }
    case "center_dominion": {
      const rounds = positiveInteger(victory.dominionRounds, 3);
      return [
        { label: "Rounds To Hold", value: quantity(rounds, "round") },
      ];
    }
    case "check_race": {
      const checks = positiveInteger(victory.checkTarget, 3);
      return [
        { label: "Checks To Win", value: quantity(checks, "check") },
      ];
    }
    default:
      return [];
  }
}
