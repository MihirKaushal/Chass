import assert from "node:assert/strict";
import test from "node:test";

import {
  resetEnabledCustomRules,
  resetEnabledGambit,
  resetEnabledSpecialAbilities,
} from "./customizeResetDefaults.js";

test("custom rule reset preserves the enabled state and restores baseline values", () => {
  assert.deepEqual(
    resetEnabledCustomRules({ affinityEnabled: false, commandPointCap: 3 }),
    { affinityEnabled: true, commandPointCap: 3 }
  );
});

test("ability reset enables compatible baseline defaults without sharing parameters", () => {
  const parameters = {
    necromancy: { cooldownRounds: 9 },
    getaway: { usesPerGame: 1 },
  };
  const reset = resetEnabledSpecialAbilities({
    defaults: { enabled: false, allowed: [], maxPerPlayer: 1 },
    abilities: [{ id: "necromancy" }, { id: "getaway" }],
    disabledAbilities: { getaway: "Requires a Queen." },
    parameters,
  });

  assert.deepEqual(reset.allowed, ["necromancy"]);
  assert.equal(reset.enabled, true);
  assert.equal(reset.maxPerPlayer, 1);
  reset.parameters.necromancy.cooldownRounds = 12;
  assert.equal(parameters.necromancy.cooldownRounds, 9);
});

test("ability reset preserves an enabled Starting System subset", () => {
  const reset = resetEnabledSpecialAbilities({
    defaults: { enabled: true, allowed: ["getaway"], maxPerPlayer: 2 },
    abilities: [{ id: "necromancy" }, { id: "getaway" }],
    parameters: {},
  });

  assert.deepEqual(reset.allowed, ["getaway"]);
  assert.equal(reset.maxPerPlayer, 1);
});

test("Gambit reset remains enabled and clamps setup rows to the current board", () => {
  const defaults = {
    enabled: false,
    budget: 39,
    maxPieces: 16,
    setupRows: 4,
    maxQueens: 2,
    draftEnabled: false,
    draftPool: { king: 2 },
  };
  const reset = resetEnabledGambit(defaults, 6);

  assert.equal(reset.enabled, true);
  assert.equal(reset.setupRows, 3);
  assert.equal(reset.budget, 39);
  reset.draftPool.king = 4;
  assert.equal(defaults.draftPool.king, 2);
});
