import assert from "node:assert/strict";
import test from "node:test";

import {
  initialCommandDisclosure,
  revealEarnedCommandPoints,
  toggleCommandDisclosure,
} from "./commandDisclosure.js";

test("command details begin closed at zero points and open for restored points", () => {
  const state = initialCommandDisclosure({ white: 0, black: 2 });
  assert.deepEqual(state.white, { expanded: false, autoOpened: false });
  assert.deepEqual(state.black, { expanded: true, autoOpened: true });
});

test("command details support manual opening before points are earned", () => {
  const state = initialCommandDisclosure({ white: 0, black: 0 });
  assert.equal(toggleCommandDisclosure(state, "white").white.expanded, true);
});

test("the first earned point opens details without overriding later manual closes", () => {
  const initial = initialCommandDisclosure({ white: 0, black: 0 });
  const earned = revealEarnedCommandPoints(initial, { white: 1, black: 0 });
  assert.deepEqual(earned.white, { expanded: true, autoOpened: true });

  const manuallyClosed = toggleCommandDisclosure(earned, "white");
  const laterUpdate = revealEarnedCommandPoints(
    manuallyClosed,
    { white: 2, black: 0 }
  );
  assert.equal(laterUpdate.white.expanded, false);
});
