import assert from "node:assert/strict";
import test from "node:test";

import { visibleCustomizePieces } from "./customizePieces.js";

const pieces = [
  { type: "pawn", name: "Pawn", isCustom: false },
  { type: "catapult", name: "Catapult", isCustom: true },
  { type: "rook", name: "Rook", isCustom: false },
  { type: "elephant", name: "Elephant", isCustom: true },
];

test("piece filters preserve catalog order while showing enabled pieces first", () => {
  assert.deepEqual(
    visibleCustomizePieces(pieces, ["rook", "elephant"], "all").map(({ type }) => type),
    ["rook", "elephant", "pawn", "catapult"]
  );
  assert.deepEqual(
    visibleCustomizePieces(pieces, ["rook", "elephant"], "enabled").map(({ type }) => type),
    ["rook", "elephant"]
  );
});

test("classic and custom filters retain enabled-first ordering", () => {
  assert.deepEqual(
    visibleCustomizePieces(pieces, ["rook", "elephant"], "classic").map(({ type }) => type),
    ["rook", "pawn"]
  );
  assert.deepEqual(
    visibleCustomizePieces(pieces, ["rook", "elephant"], "custom").map(({ type }) => type),
    ["elephant", "catapult"]
  );
});
