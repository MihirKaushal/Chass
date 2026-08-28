import assert from "node:assert/strict";
import test from "node:test";

import { specialRulePresentation } from "./specialRulePresentation.js";

const affinityRules = [
  "affinity_control",
  "command_points",
  "gambit_pawn_reinforcement",
  "gambit_pawn_evolution",
  "gambit_rook_stronghold",
].map((id) => ({
  id,
  enabled: true,
  isSpecial: true,
  tier: "custom",
  displayGroup: "affinity",
}));

test("Affinity command rules appear as one enabled Special Rules item", () => {
  const presentation = specialRulePresentation({
    affinity: { enabled: true },
    rules: affinityRules,
  });

  assert.deepEqual(presentation.rules, []);
  assert.deepEqual(presentation.itemKeys, ["affinity_command_system"]);
  assert.equal(presentation.affinityEnabled, true);
});

test("standalone special rules remain separate from the Affinity group", () => {
  const timedRule = {
    id: "configured_victory",
    enabled: true,
    isSpecial: true,
    tier: "victory",
  };
  const presentation = specialRulePresentation({
    affinity: { enabled: true },
    rules: [timedRule, ...affinityRules],
  });

  assert.deepEqual(presentation.rules, [timedRule]);
  assert.deepEqual(
    presentation.itemKeys,
    ["configured_victory", "affinity_command_system"]
  );
});

test("legacy Affinity responses are grouped without display metadata", () => {
  const presentation = specialRulePresentation({
    affinity: { enabled: true },
    rules: affinityRules.map(({ displayGroup, ...rule }) => rule),
  });

  assert.deepEqual(presentation.rules, []);
  assert.deepEqual(presentation.itemKeys, ["affinity_command_system"]);
});
