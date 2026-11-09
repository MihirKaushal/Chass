const LEGACY_AFFINITY_RULE_IDS = new Set([
  "affinity_control",
  "command_points",
  "gambit_pawn_reinforcement",
  "gambit_pawn_evolution",
  "gambit_rook_stronghold",
]);

function isAffinityCommandRule(rule) {
  return rule.displayGroup === "affinity" || LEGACY_AFFINITY_RULE_IDS.has(rule.id);
}

export function specialRulePresentation(game = {}) {
  const activeRules = (game.rules || []).filter(
    (rule) => rule.enabled && (rule.isSpecial || rule.tier !== "basic")
  );
  const rules = activeRules.filter((rule) => !isAffinityCommandRule(rule));
  const affinityEnabled = Boolean(game.affinity?.enabled);

  return {
    rules,
    affinityEnabled,
    itemKeys: [
      ...rules.map((rule) => rule.id),
      ...(affinityEnabled ? ["affinity_command_system"] : []),
    ],
  };
}
