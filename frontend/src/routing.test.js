import assert from "node:assert/strict";
import test from "node:test";

import { routeFromPath, shouldHandleAppLink } from "./routing.js";

test("the Rulebook has a dedicated route", () => {
  assert.deepEqual(routeFromPath("/rulebook"), { name: "rulebook" });
  assert.deepEqual(routeFromPath("/rulebook/"), { name: "rulebook" });
});

test("Scanner is a first-class same-tab route", () => {
  assert.deepEqual(routeFromPath("/scanner"), { name: "scanner" });
  assert.deepEqual(routeFromPath("/scanner/"), { name: "scanner" });
});

test("customize presets are parsed from the supplied search string", () => {
  assert.deepEqual(routeFromPath("/customize", "?preset=gambit"), {
    name: "customize",
    preset: "gambit",
  });
});

function linkEvent(overrides = {}, anchor = {}) {
  return {
    button: 0,
    currentTarget: { target: "", origin: "https://playchass.vercel.app", hasAttribute: () => false, ...anchor },
    ...overrides,
  };
}

test("ordinary Rulebook link clicks use same-tab client-side navigation", () => {
  assert.equal(shouldHandleAppLink(linkEvent(), "https://playchass.vercel.app"), true);
});

test("navigation links respect modifier keys, external URLs, downloads, and cancelled events", () => {
  const origin = "https://playchass.vercel.app";
  for (const event of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { defaultPrevented: true }]) {
    assert.equal(shouldHandleAppLink(linkEvent(event), origin), false);
  }
  assert.equal(shouldHandleAppLink(linkEvent({}, { target: "_blank" }), origin), false);
  assert.equal(shouldHandleAppLink(linkEvent({}, { origin: "https://example.com" }), origin), false);
  assert.equal(shouldHandleAppLink(linkEvent({}, { hasAttribute: () => true }), origin), false);
});
