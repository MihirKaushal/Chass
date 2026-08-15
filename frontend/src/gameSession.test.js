import assert from "node:assert/strict";
import test from "node:test";

import { playerHasAbility } from "./gameSession.js";

test("playerHasAbility reads list-shaped selections", () => {
  const game = {
    abilities: {
      selected: {
        white: ["getaway", "kamikaze"],
        black: ["episcopal"],
      },
    },
  };

  assert.equal(playerHasAbility(game, "white", "kamikaze"), true);
  assert.equal(playerHasAbility(game, "black", "kamikaze"), false);
});

test("playerHasAbility supports legacy single selections", () => {
  const game = { abilities: { selected: { white: "kamikaze" } } };

  assert.equal(playerHasAbility(game, "white", "kamikaze"), true);
  assert.equal(playerHasAbility(game, "black", "kamikaze"), false);
});
