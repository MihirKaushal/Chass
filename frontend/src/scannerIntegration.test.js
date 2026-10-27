import assert from "node:assert/strict";
import { before, after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
before(async () => {
  server = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    logLevel: "silent",
    server: { middlewareMode: true, hmr: false, watch: null },
  });
});
after(async () => {
  await server?.close();
});

async function markup(path, props) {
  const { default: Component } = await server.ssrLoadModule(path);
  return renderToStaticMarkup(createElement(Component, props));
}

test("landing and play navigation both expose the same-tab scanner link", async () => {
  for (const path of [
    "/src/components/LandingNav.jsx",
    "/src/components/TopNav.jsx",
  ]) {
    const html = await markup(path, {
      onHome() {},
      onCustomize() {},
      phase: "play",
      currentPlayer: "white",
    });
    assert.match(html, /href="\/scanner"/);
    assert.doesNotMatch(html, /target="_blank"/);
  }
  const active = await markup("/src/components/LandingNav.jsx", {
    active: "scanner",
  });
  assert.match(active, /aria-current="page">Scanner<\/span>/);
});

test("rulebook includes a searchable scanner section and return link", async () => {
  const html = await markup("/src/components/RulebookReference.jsx", {
    catalog: {
      pieces: [],
      specialAbilities: [],
      victoryModes: [],
      gambit: {
        icon: "",
        name: "Chass Gambit",
        summary: "",
        details: [],
        draftDetails: [],
      },
    },
  });
  assert.match(html, /id="rulebook-scanner"/);
  assert.match(html, /href="#rulebook-scanner"/);
  assert.match(html, /href="\/scanner"/);
  assert.match(html, /ResNet18/);
  assert.match(html, /not available yet/);
});

test("scanner status and future game controls do not imply unavailable features work", async () => {
  const offline = await markup(
    "/src/components/scanner/ScannerServiceStatus.jsx",
    { status: "offline" },
  );
  assert.match(offline, /Recognition Offline/);
  assert.match(offline, /Retry Connection/);
  const unconfigured = await markup(
    "/src/components/scanner/ScannerServiceStatus.jsx",
    { status: "unconfigured" },
  );
  assert.match(unconfigured, /Photo Preparation Only/);
  assert.doesNotMatch(unconfigured, /Retry Connection/);
  const upcoming = await markup(
    "/src/components/scanner/ScannerContinuePanel.jsx",
  );
  assert.equal((upcoming.match(/disabled=""/g) || []).length, 3);
  assert.doesNotMatch(upcoming, /<select|type="radio"/);
});
