import assert from "node:assert/strict";
import test from "node:test";

import {
  effectOwnerDescriptor,
  effectPerspectiveColor,
  pieceCountsByOwner,
} from "./effectOwnership.js";

test("online ownership follows the authenticated player seat", () => {
  const game = { mode: "online", currentPlayer: "black" };
  const perspective = effectPerspectiveColor(game, "white");

  assert.equal(perspective, "white");
  assert.deepEqual(effectOwnerDescriptor("white", perspective, game.mode), {
    label: "You · White",
    relation: "self",
  });
  assert.deepEqual(effectOwnerDescriptor("black", perspective, game.mode), {
    label: "Opponent · Black",
    relation: "opponent",
  });
});

test("local ownership follows the player whose turn is active", () => {
  const game = { mode: "local", currentPlayer: "black" };
  const perspective = effectPerspectiveColor(game);

  assert.equal(perspective, "black");
  assert.equal(
    effectOwnerDescriptor("black", perspective, game.mode).label,
    "Current Player · Black"
  );
  assert.equal(
    effectOwnerDescriptor("white", perspective, game.mode).label,
    "Other Player · White"
  );
});

test("bot ownership falls back to the configured human side", () => {
  const game = { mode: "bot", bot: { humanColor: "black" } };

  assert.equal(effectPerspectiveColor(game), "black");
});

test("custom-piece counts keep neutral pieces separate", () => {
  const board = [
    [
      { type: "catapult", color: "white" },
      { type: "catapult", color: "black" },
      { type: "barricade", color: "neutral" },
    ],
    [{ type: "catapult", color: "white" }, null, null],
  ];

  assert.deepEqual(pieceCountsByOwner(board, "catapult"), {
    white: 2,
    black: 1,
    neutral: 0,
  });
  assert.deepEqual(effectOwnerDescriptor("neutral", "white", "online"), {
    label: "Neutral · Shared",
    relation: "neutral",
  });
});
