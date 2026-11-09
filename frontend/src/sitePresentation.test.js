import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("scanner glow animates only its shadow and respects reduced motion", () => {
  const css = readFileSync(new URL("./styles/scanner.css", import.meta.url), "utf8");
  assert.match(css, /\.scanner-feature-card\s*\{[^}]*animation: scanner-card-glow 12s ease-in-out infinite;/);
  const keyframes = css.match(/@keyframes scanner-card-glow\s*\{([\s\S]*?)\n\}/)?.[1];
  assert.ok(keyframes);
  assert.equal((keyframes.match(/box-shadow:/g) || []).length, 4);
  assert.doesNotMatch(keyframes, /transform:|width:|height:|margin:|padding:/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.scanner-feature-card\s*\{\s*animation: none;/);
});
