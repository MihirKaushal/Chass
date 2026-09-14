import test from "node:test";
import assert from "node:assert/strict";

import { pieceTapIntent } from "./pieceTap.js";

test("the first piece tap activates immediately and the second opens details", () => {
  const first = pieceTapIntent({
    detailsMode: "double-tap",
    hasPiece: true,
    clickCount: 1,
    squareKey: "6-4",
    pendingSquareKey: null,
  });
  const second = pieceTapIntent({
    detailsMode: "double-tap",
    hasPiece: true,
    clickCount: 1,
    squareKey: "6-4",
    pendingSquareKey: "6-4",
  });

  assert.equal(first, "activate");
  assert.equal(second, "details");
});

test("empty squares and different pieces remain immediate board actions", () => {
  assert.equal(pieceTapIntent({
    detailsMode: "double-tap",
    hasPiece: false,
    clickCount: 1,
    squareKey: "4-4",
    pendingSquareKey: "6-4",
  }), "activate");
  assert.equal(pieceTapIntent({
    detailsMode: "double-tap",
    hasPiece: true,
    clickCount: 1,
    squareKey: "6-3",
    pendingSquareKey: "6-4",
  }), "activate");
});
