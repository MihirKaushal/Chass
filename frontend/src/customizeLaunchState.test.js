import assert from "node:assert/strict";
import test from "node:test";

import { customizeLaunchState } from "./customizeLaunchState.js";

test("launch status reports a validated configuration as ready", () => {
  assert.deepEqual(
    customizeLaunchState(
      { status: "valid", valid: true, requestKey: "current" },
      "current"
    ),
    {
      heading: "Ready to Play",
      detail: "Configuration valid",
      errors: [],
      warning: "",
    }
  );
});

test("launch status uses an exact singular or plural issue count", () => {
  assert.equal(
    customizeLaunchState(
      { status: "invalid", valid: false, errors: ["One problem"], requestKey: "one" },
      "one"
    ).heading,
    "Fix 1 Issue"
  );
  assert.equal(
    customizeLaunchState(
      {
        status: "invalid",
        valid: false,
        errors: ["First problem", "Second problem"],
        requestKey: "two",
      },
      "two"
    ).heading,
    "Fix 2 Issues"
  );
});

test("launch status hides stale validation while a new setup is checked", () => {
  const state = customizeLaunchState(
    { status: "valid", valid: true, requestKey: "previous" },
    "current"
  );

  assert.equal(state.heading, "Checking Setup");
  assert.deepEqual(state.errors, []);
});

test("launch status reports a validation request failure as an issue", () => {
  const state = customizeLaunchState(
    {
      status: "invalid",
      valid: false,
      errors: ["Validation service unavailable"],
      requestKey: null,
    },
    "current"
  );

  assert.equal(state.heading, "Fix 1 Issue");
  assert.deepEqual(state.errors, ["Validation service unavailable"]);
});
