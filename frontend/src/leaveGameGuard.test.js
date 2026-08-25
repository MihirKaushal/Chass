import assert from "node:assert/strict";
import test from "node:test";

import {
  recordedTurnCount,
  shouldConfirmCustomizeNavigation,
  shouldConfirmDiscardingCustomization,
} from "./leaveGameGuard.js";

test("Customize navigation is immediate before the first turn", () => {
  const game = {
    phase: "play",
    winner: null,
    history: [],
    historyPagination: { totalMoves: 0 },
  };

  assert.equal(recordedTurnCount(game), 0);
  assert.equal(shouldConfirmCustomizeNavigation(game), false);
});

test("Customize navigation requires confirmation after play begins", () => {
  const game = {
    phase: "play",
    winner: null,
    history: [],
    historyPagination: { totalMoves: 4 },
  };

  assert.equal(recordedTurnCount(game), 4);
  assert.equal(shouldConfirmCustomizeNavigation(game), true);
});

test("Finished and setup games do not show the leave-game warning", () => {
  assert.equal(
    shouldConfirmCustomizeNavigation({
      phase: "finished",
      winner: "white",
      history: [{ moveNumber: 1 }],
    }),
    false
  );
  assert.equal(
    shouldConfirmCustomizeNavigation({
      phase: "ability_selection",
      winner: null,
      history: [{ moveNumber: 1 }],
    }),
    false
  );
});

test("Home navigation warns only when the Customize configuration changed", () => {
  assert.equal(shouldConfirmDiscardingCustomization(true), true);
  assert.equal(shouldConfirmDiscardingCustomization(false), false);
  assert.equal(shouldConfirmDiscardingCustomization(undefined), false);
});
