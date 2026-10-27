import assert from "node:assert/strict";
import test from "node:test";
import { SITE_SECTIONS, navigationDestination } from "./siteNavigation.js";
import { matchesRulebookSearch } from "./rulebookSearch.js";
import { SCANNER_REFERENCE } from "./scannerReference.js";

test("every shared navigation uses one ordered set of destinations", () => {
  assert.deepEqual(
    SITE_SECTIONS.map(({ id }) => id),
    ["home", "customize", "scanner", "rulebook"],
  );
  assert.equal(new Set(SITE_SECTIONS.map(({ href }) => href)).size, 4);
});

test("leaving a game names Scanner correctly, including a deep link", () => {
  for (const path of ["/scanner", "/scanner/", "/scanner?from=play"]) {
    assert.equal(navigationDestination(path).destination, "the Board Scanner");
    assert.equal(navigationDestination(path).leaveLabel, "Open Scanner");
  }
  assert.equal(
    navigationDestination("/rulebook#rulebook-scanner").destination,
    "the Rulebook",
  );
  assert.equal(
    navigationDestination("/customize?preset=gambit").destination,
    "Customize",
  );
  assert.equal(navigationDestination("/unknown").leaveLabel, "Leave Game");
});

test("rulebook search finds scanner instructions, models, limits and privacy", () => {
  for (const query of [
    "scanner",
    "crop",
    "ResNet18",
    "castl",
    "en passant",
    "third-party",
    "64-square",
    "offline",
  ]) {
    assert.equal(matchesRulebookSearch(query, SCANNER_REFERENCE), true, query);
  }
  assert.equal(matchesRulebookSearch("scorch", SCANNER_REFERENCE), false);
});
