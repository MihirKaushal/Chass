import assert from "node:assert/strict";
import test from "node:test";
import { readGamePreferences, saveGamePreferences, GAME_PREFERENCES_KEY } from "./gamePreferences.js";
function storage() {
  const entries = new Map();
  return { getItem: (key) => entries.get(key), setItem: (key, value) => entries.set(key, value) };
}
test("default auto flip is local only; remote games face the player's seat", () => {
  for (const mode of ["local", "online", "bot"]) {
    const prefs = readGamePreferences(null, { gameId: "g", mode, color: mode === "local" ? null : "black" });
    assert.equal(prefs.autoFlip, mode === "local");
    assert.equal(prefs.flipped, mode !== "local");
  }
});
test("game settings survive reload and mode defaults do not leak between room types", () => {
  const store = storage(), context = { gameId: "g", mode: "local" };
  const prefs = { autoFlip: false, flipped: true, analysis: false };
  saveGamePreferences(store, context, prefs);
  assert.deepEqual(readGamePreferences(store, context), prefs);
  assert.deepEqual(readGamePreferences(store, { ...context, gameId: "new" }), { ...prefs, flipped: false });
  assert.equal(readGamePreferences(store, { gameId: "online", mode: "online" }).analysis, true);
});
test("online seat preferences stay separate and storage stays bounded", () => {
  const store = storage();
  saveGamePreferences(store, { gameId: "g", mode: "online", color: "white" }, { autoFlip: false, flipped: false, analysis: false });
  saveGamePreferences(store, { gameId: "g", mode: "online", color: "black" }, { autoFlip: true, flipped: true, analysis: true });
  assert.equal(readGamePreferences(store, { gameId: "g", mode: "online", color: "white" }).autoFlip, false);
  for (let index = 0; index < 50; index++) saveGamePreferences(store, { gameId: `${index}`, mode: "local" }, { autoFlip: true });
  assert.equal(Object.keys(JSON.parse(store.getItem(GAME_PREFERENCES_KEY)).games).length, 32);
});
test("unavailable or malformed storage does not prevent play", () => {
  assert.equal(readGamePreferences({ getItem: () => "broken" }, { mode: "local" }).autoFlip, true);
  assert.doesNotThrow(() => saveGamePreferences({ setItem: () => { throw Error("denied"); } }, { gameId: "g", mode: "bot" }, { autoFlip: false }));
});
