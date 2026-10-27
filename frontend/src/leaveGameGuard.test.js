import assert from "node:assert/strict";
import test from "node:test";

import {
  shouldConfirmGameNavigation,
  shouldConfirmDiscardingCustomization,
} from "./leaveGameGuard.js";

test("game navigation requires confirmation before the first turn", () => {
  const game = {
    phase: "play",
    winner: null,
    history: [],
    historyPagination: { totalMoves: 0 },
  };

  assert.equal(shouldConfirmGameNavigation(game), true);
});

test("game navigation requires confirmation after play begins", () => {
  const game = {
    phase: "play",
    winner: null,
    history: [],
    historyPagination: { totalMoves: 4 },
  };

  assert.equal(shouldConfirmGameNavigation(game), true);
});

test("setup phases are protected while finished and missing games are not", () => {
  assert.equal(
    shouldConfirmGameNavigation({
      phase: "finished",
      winner: "white",
      history: [{ moveNumber: 1 }],
    }),
    false
  );
  assert.equal(
    shouldConfirmGameNavigation({
      phase: "ability_selection",
      winner: null,
      history: [],
    }),
    true
  );
  assert.equal(shouldConfirmGameNavigation(null), false);
});

test("Home navigation warns only when the Customize configuration changed", () => {
  assert.equal(shouldConfirmDiscardingCustomization(true), true);
  assert.equal(shouldConfirmDiscardingCustomization(false), false);
  assert.equal(shouldConfirmDiscardingCustomization(undefined), false);
});

test("reading the Rulebook preserves the customizer instead of prompting to discard it", () => {
  for (const destination of ["/rulebook", "/rulebook/", "/rulebook#rulebook-pieces", "/rulebook?search=pawn"]) {
    assert.equal(shouldConfirmDiscardingCustomization(true, destination), false);
  }
  assert.equal(shouldConfirmDiscardingCustomization(true, "/"), true);
  assert.equal(shouldConfirmDiscardingCustomization(true, "/game/123"), true);
  assert.equal(shouldConfirmDiscardingCustomization(true, "/rulebook-other"), true);
});

test("visiting Scanner keeps the customizer draft without bypassing other leave guards", () => {
  for (const destination of ["/scanner", "/scanner/", "/scanner?from=customize"]) {
    assert.equal(shouldConfirmDiscardingCustomization(true, destination), false);
  }
  assert.equal(shouldConfirmDiscardingCustomization(true, "/scanner-other"), true);
  assert.equal(shouldConfirmGameNavigation({ phase: "play", history: [] }), true);
});
