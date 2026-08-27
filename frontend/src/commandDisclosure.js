const PLAYER_COLORS = ["white", "black"];

export function initialCommandDisclosure(commandPoints = {}) {
  return Object.fromEntries(
    PLAYER_COLORS.map((color) => {
      const hasPoints = (commandPoints[color] || 0) >= 1;
      return [color, { expanded: hasPoints, autoOpened: hasPoints }];
    })
  );
}

export function revealEarnedCommandPoints(current, commandPoints = {}) {
  let changed = false;
  const next = { ...current };
  PLAYER_COLORS.forEach((color) => {
    if ((commandPoints[color] || 0) >= 1 && !current[color]?.autoOpened) {
      next[color] = { expanded: true, autoOpened: true };
      changed = true;
    }
  });
  return changed ? next : current;
}

export function toggleCommandDisclosure(current, color) {
  return {
    ...current,
    [color]: {
      ...current[color],
      expanded: !current[color]?.expanded,
    },
  };
}
