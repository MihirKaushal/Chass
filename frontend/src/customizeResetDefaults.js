function copyParameterGroups(groups = {}) {
  return Object.fromEntries(
    Object.entries(groups).map(([id, values]) => [id, { ...values }])
  );
}

export function resetEnabledCustomRules(defaults = {}) {
  return {
    ...defaults,
    affinityEnabled: true,
  };
}

export function resetEnabledSpecialAbilities({
  defaults = {},
  abilities = [],
  disabledAbilities = {},
  parameters = {},
}) {
  const compatibleIds = abilities
    .filter((ability) => !disabledAbilities[ability.id])
    .map((ability) => ability.id);
  const baselineAllowed = defaults.enabled
    ? (defaults.allowed || []).filter((id) => compatibleIds.includes(id))
    : compatibleIds;
  const allowed = baselineAllowed.length ? baselineAllowed : compatibleIds;
  const requestedMaximum = Math.max(1, Number(defaults.maxPerPlayer) || 1);

  return {
    ...defaults,
    enabled: true,
    allowed,
    maxPerPlayer: Math.min(requestedMaximum, Math.max(1, allowed.length)),
    parameters: copyParameterGroups(parameters),
  };
}

export function resetEnabledGambit(defaults = {}, boardRows = 8) {
  const maximumSetupRows = Math.max(1, Math.floor(Number(boardRows) / 2));
  return {
    ...defaults,
    enabled: true,
    setupRows: Math.min(
      Math.max(1, Number(defaults.setupRows) || 1),
      maximumSetupRows
    ),
    draftPool: { ...(defaults.draftPool || {}) },
  };
}
