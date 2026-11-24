import assert from "node:assert/strict";
import test from "node:test";

import { importWithReload } from "./lazyRoute.js";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test("a missing chunk reloads the page once", async () => {
  const storage = memoryStorage();
  let reloads = 0;
  const pending = importWithReload(() => Promise.reject(new Error("chunk")), {
    storage,
    reload: () => { reloads += 1; },
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(reloads, 1);
  assert.equal(await Promise.race([pending, Promise.resolve("still pending")]), "still pending");

  await assert.rejects(
    importWithReload(() => Promise.reject(new Error("chunk")), { storage, reload: () => { reloads += 1; } }),
    /chunk/
  );
  assert.equal(reloads, 1);
});

test("a successful load clears the reload guard", async () => {
  const storage = memoryStorage();
  storage.setItem("chass:chunk-reload", "1");
  const module = await importWithReload(() => Promise.resolve({ default: "page" }), { storage });
  assert.equal(module.default, "page");
  assert.equal(storage.getItem("chass:chunk-reload"), null);
});
