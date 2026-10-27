import assert from "node:assert/strict";
import { before, after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { defaultScannerDetails } from "./scannerReview.js";

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
  assert.match(html, /experimental/);
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

test("scanner launch requires confirmation, resolved flags and a valid position; bots stay disabled", async () => {
  const path = "/src/components/scanner/ScannerContinuePanel.jsx";
  const ready = {
    confirmed: true,
    remainingReviews: 0,
    validation: { valid: true, issues: [] },
  };
  assert.equal(
    ((await markup(path, ready)).match(/disabled=""/g) || []).length,
    1,
  );
  for (const blocked of [
    { confirmed: false },
    { remainingReviews: 1 },
    { validating: true },
    { busy: true },
    { validation: { valid: false, issues: [] } },
  ]) {
    assert.equal(
      (
        (await markup(path, { ...ready, ...blocked })).match(/disabled=""/g) ||
        []
      ).length,
      3,
    );
  }
});

test("flagged squares expose selectable alternatives, empty and keep-current options", async () => {
  const { scannerPreviewPiece } = await server.ssrLoadModule(
    "/src/components/scanner/scannerPreview.js",
  );
  const board = Array.from({ length: 8 }, () => Array(8).fill(null));
  board[3][4] = scannerPreviewPiece("bishop", "white", 3, 4);
  const html = await markup("/src/components/scanner/ScannerBoardReview.jsx", {
    board,
    reviewSquares: [
      { row: 3, col: 4, label: "e5", reasons: ["Low model confidence"] },
    ],
    scan: {
      squareCandidates: [
        {
          row: 3,
          col: 4,
          candidates: [
            {
              class: "white-bishop",
              classifierScore: 0.55,
              alternatives: [{ label: "white-queen", score: 0.4 }],
            },
          ],
        },
      ],
    },
  });
  assert.match(html, /Review e5/);
  assert.match(html, /White bishop/);
  assert.match(html, /White queen/);
  assert.match(html, /55%/);
  assert.match(html, /This Square Is Empty/);
  assert.match(html, /Keep Current Piece/);
});

test("optional history controls reflect the controlled position and block unresolved confirmation", async () => {
  const html = await markup(
    "/src/components/scanner/ScannerPositionDetails.jsx",
    {
      details: { ...defaultScannerDetails(), fullmoveNumber: 23 },
      confirmed: false,
      remainingReviews: 1,
    },
  );
  assert.match(html, /value="23"/);
  assert.match(html, /Halfmove clock/);
  assert.match(html, /type="checkbox" disabled=""/);
});
