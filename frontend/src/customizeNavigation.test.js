import assert from "node:assert/strict";
import test from "node:test";

import {
  CUSTOMIZE_SECTION_LINKS,
  matchingCustomizeSections,
} from "./customizeNavigation.js";

test("an empty customize search preserves every section in page order", () => {
  assert.deepEqual(
    matchingCustomizeSections("").map(({ id }) => id),
    CUSTOMIZE_SECTION_LINKS.map(({ id }) => id)
  );
});

test("customize search finds sections by setting and item names", () => {
  assert.deepEqual(
    matchingCustomizeSections("timer").map(({ label }) => label),
    ["End Game Logic"]
  );
  assert.deepEqual(
    matchingCustomizeSections("catapult").map(({ label }) => label),
    ["Pieces"]
  );
  assert.deepEqual(
    matchingCustomizeSections("board dimensions").map(({ label }) => label),
    ["Board Size"]
  );
  assert.deepEqual(
    matchingCustomizeSections("reference").map(({ label }) => label),
    ["Rulebook"]
  );
});
