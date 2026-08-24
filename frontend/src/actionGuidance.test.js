import assert from "node:assert/strict";
import test from "node:test";

import { buildActionGuidance } from "./actionGuidance.js";

const game = {
  currentPlayer: "white",
  board: [
    [null, null, null],
    [null, { name: "Catapult", isCustom: true, movement: "Moves one square forward." }, null],
    [null, null, null],
  ],
  validMoves: [
    { from: { row: 1, col: 1 }, to: { row: 0, col: 1 } },
  ],
  availableActions: [
    {
      actionType: "scorch",
      boardMarker: "scorch",
      icon: "S",
      label: "Scorch Square",
      description: "Block the square.",
      target: { row: 0, col: 0 },
    },
  ],
};

test("guidance covers normal custom movement and explicit special actions", () => {
  const movement = buildActionGuidance({
    game,
    selectedSquare: { row: 1, col: 1 },
  });
  assert.equal(movement.title, "Catapult selected");
  assert.equal(movement.description, "Moves one square forward.");

  const projectile = buildActionGuidance({
    game,
    selectedBoardAction: {
      source: { row: 1, col: 1 },
      actions: [{
        actionType: "catapult_projectile",
        boardMarker: "attack",
        icon: "T",
      }],
    },
  });
  assert.equal(projectile.title, "Catapult projectile ready");
  assert.equal(projectile.marker, "attack");
});

test("guidance covers global abilities and command powers", () => {
  const scorch = buildActionGuidance({ game, selectedGlobalActionType: "scorch" });
  assert.equal(scorch.title, "Scorch ready");
  assert.equal(scorch.marker, "scorch");

  const evolve = buildActionGuidance({
    game,
    selectedPower: "evolve",
    powerTargets: [{ row: 1, col: 1 }],
  });
  assert.equal(evolve.title, "Evolve command ready");
  assert.match(evolve.description, /1 legal target/);
});

test("idle turn guidance does not request an information marker", () => {
  const idle = buildActionGuidance({ game });
  assert.equal(idle.title, "White to move");
  assert.equal(idle.marker, null);
  assert.equal(idle.icon, null);
});
