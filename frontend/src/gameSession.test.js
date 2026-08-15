import assert from "node:assert/strict";
import test from "node:test";

import { mergeHistoryRecords, playerHasAbility } from "./gameSession.js";

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

test("mergeHistoryRecords orders pages and removes overlap", () => {
  const merged = mergeHistoryRecords(
    [{ moveNumber: 2, explanation: "older" }, { moveNumber: 3 }],
    [{ moveNumber: 1 }, { moveNumber: 2, explanation: "newer" }]
  );

  assert.deepEqual(merged.map((record) => record.moveNumber), [1, 2, 3]);
  assert.equal(merged[1].explanation, "newer");
});
