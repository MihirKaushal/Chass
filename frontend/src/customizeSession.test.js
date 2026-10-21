import assert from "node:assert/strict";
import test from "node:test";

import { createCustomizeSessionStore } from "./customizeSession.js";

function tabStorage(initial = []) {
  const values = new Map(initial);
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

function snapshot() {
  return {
    initialPreset: "gambit",
    path: "/customize?preset=gambit#studio-pieces",
    draft: {
      boardRows: 10,
      boardCols: 12,
      enabledPieces: ["king", "pawn", "elephant"],
      placements: [{ row: 9, col: 4, type: "king", color: "white" }],
      pointValues: { pawn: 2, elephant: 7 },
      pieceCaps: { pawn: 15, elephant: 3 },
      pieceParameters: { elephant: { chargeDistance: 3 } },
      victory: { mode: "point_race", targetPoints: 30 },
      customRules: { affinityEnabled: true, commandPointCap: 4 },
      specialAbilities: {
        enabled: true,
        allowed: ["scorch"],
        parameters: { scorch: { cooldown: 8 } },
      },
      gambit: { enabled: true, budget: 50 },
    },
    configurationBaseline: { boardRows: 8 },
    pageEntryBaseline: { boardRows: 8 },
    boardHistory: [[{ row: 7, col: 4, type: "king", color: "white" }]],
    restoreFormationId: "classic",
    selectedTool: { type: "pawn", color: "white" },
  };
}

test("customizer settings, board history, and modification baselines survive a page reload", () => {
  const storage = tabStorage();
  const store = createCustomizeSessionStore(() => storage);
  const saved = snapshot();
  store.save(saved);
  const restored = createCustomizeSessionStore(() => storage);
  assert.deepEqual(restored.read(), { ...saved, version: 1 });
  assert.equal(restored.returnPath(), saved.path);
});

test("the customizer keeps a memory fallback if browser storage is unavailable", () => {
  const store = createCustomizeSessionStore(() => {
    throw new Error("Blocked");
  });
  assert.equal(store.read(), null);
  store.save(snapshot());
  assert.deepEqual(store.read().draft, snapshot().draft);
  store.clear();
  assert.equal(store.read(), null);
});

test("quota errors do not prevent returning to the current configuration", () => {
  const storage = tabStorage();
  storage.setItem = () => {
    throw new Error("Quota exceeded");
  };
  const store = createCustomizeSessionStore(() => storage);
  store.save(snapshot());
  assert.equal(store.read().draft.boardCols, 12);
});

test("discarding or launching a game removes the saved customizer session", () => {
  const storage = tabStorage();
  const store = createCustomizeSessionStore(() => storage);
  store.save(snapshot());
  store.clear();
  assert.equal(store.read(), null);
  assert.equal(createCustomizeSessionStore(() => storage).read(), null);
  assert.equal(store.returnPath(), "/customize");
});

test("corrupt, incomplete, and outdated saved sessions are ignored", () => {
  for (const value of [
    "not JSON",
    "null",
    "{}",
    JSON.stringify({ ...snapshot(), version: 0 }),
    JSON.stringify({ ...snapshot(), version: 1, draft: {} }),
  ]) {
    const store = createCustomizeSessionStore(() =>
      tabStorage([["chass-customizer-session", value]]),
    );
    assert.equal(store.read(), null);
    assert.equal(store.returnPath(), "/customize");
  }
});

test("return links only restore local customizer routes", () => {
  const store = createCustomizeSessionStore(() => tabStorage());
  for (const path of [
    "https://example.com/customize",
    "//example.com/customize",
    "/game/123",
    "/customize-other",
    "javascript:alert(1)",
  ]) {
    store.save({ ...snapshot(), path });
    assert.equal(store.returnPath(), "/customize");
  }
  store.save({ ...snapshot(), path: "/gambit" });
  assert.equal(store.returnPath(), "/gambit");
});
