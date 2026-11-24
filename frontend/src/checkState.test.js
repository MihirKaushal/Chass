import assert from "node:assert/strict";
import test from "node:test";

import { checkedKingColor } from "./checkState.js";

test("the side to move's King is highlighted while in check", () => {
  assert.equal(checkedKingColor({ gameStatus: "check", currentPlayer: "black" }), "black");
});

test("the losing King is highlighted after checkmate", () => {
  assert.equal(
    checkedKingColor({ gameStatus: "checkmate", currentPlayer: "white", winner: "black" }),
    "white"
  );
});

test("no King is highlighted otherwise", () => {
  assert.equal(checkedKingColor({ gameStatus: "active", currentPlayer: "white" }), null);
  assert.equal(checkedKingColor({ gameStatus: "stalemate", currentPlayer: "white" }), null);
  assert.equal(checkedKingColor({ gameStatus: "checkmate", winner: null }), null);
  assert.equal(checkedKingColor(null), null);
});
