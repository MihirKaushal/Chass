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

test("rulebook first render includes the full reference without waiting for any API", async () => {
  const previousFetch = globalThis.fetch;
  let requests = 0;
  globalThis.fetch = () => {
    requests += 1;
    throw new Error("Backend is unavailable");
  };
  try {
    const html = await markup("/src/pages/RulebookPage.jsx");
    for (const section of ["match-analysis", "bots", "scanner", "pieces", "victory", "custom-rules", "abilities", "gambit"]) {
      assert.match(html, new RegExp(`id="rulebook-${section}"`));
      assert.match(html, new RegExp(`href="#rulebook-${section}"`));
    }
    for (const entry of ["Catapult", "Necromancy", "Royal Center", "Chass Gambit"]) {
      assert.ok(html.includes(entry), entry);
    }
    assert.match(html, /aria-label="Default value">\*<\/sup>/);
    assert.match(html, /Starting value; editable in the Game Customizer/);
    assert.doesNotMatch(html, /skeleton|rulebook-load-error|>Default<\/span>/);
    assert.equal(requests, 0);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("shared footer links the developer name to GitHub in a safe new tab", async () => {
  const html = await markup("/src/components/SiteFooter.jsx");
  assert.match(html, /Developed by <a href="https:\/\/github.com\/MihirKaushal" target="_blank" rel="noopener noreferrer">Mihir Kaushal<\/a>/);
});

test("all external Rulebook links open safely in new tabs while internal links stay in Chass", async () => {
  const html = await markup("/src/pages/RulebookPage.jsx");
  const anchors = html.match(/<a\b[^>]*>/g) || [];
  const external = anchors.filter((anchor) => /href="https?:\/\//.test(anchor));
  assert.equal(external.length, 2);
  assert.ok(external.some((anchor) => anchor.includes("ACCURACY_TRACKER.md")));
  for (const anchor of external) {
    assert.match(anchor, /target="_blank"/);
    assert.match(anchor, /rel="noopener noreferrer"/);
  }
  for (const anchor of anchors.filter((anchor) => !external.includes(anchor))) {
    assert.doesNotMatch(anchor, /target="_blank"/);
  }
});

test("home keeps concise room descriptions and exposes the scanner", async () => {
  const html = await markup("/src/pages/HomePage.jsx");
  assert.match(html, /Pass one screen between players\.<\/p>/);
  assert.match(html, /Create a private link and play from two browsers\.<\/p>/);
  assert.match(html, /Continue Your Physical Game/);
  assert.match(html, /class="page-frame home-page"/);
  assert.match(html, /class="site-footer"/);
  assert.doesNotMatch(html, /No invite required|anywhere/);
});

test("scanner status and launch controls do not imply unavailable features work", async () => {
  const offline = await markup(
    "/src/components/scanner/ScannerServiceStatus.jsx",
    { status: "offline" },
  );
  assert.match(offline, /Recognition Offline/);
  assert.match(offline, /Retry Connection/);
  assert.doesNotMatch(offline, /Start or reconnect the scanner service/);
  const warming = await markup(
    "/src/components/scanner/ScannerServiceStatus.jsx", { status: "warming" },
  );
  assert.match(warming, /Starting Scanner/);
  assert.match(warming, /aria-busy="true"/);
  assert.match(warming, /ui-status-spinner/);
  assert.doesNotMatch(warming, /Offline|Retry Connection/);
  const connected = await markup(
    "/src/components/scanner/ScannerServiceStatus.jsx", { status: "ready" },
  );
  assert.match(connected, /Scanner Ready/);
  assert.doesNotMatch(connected, /<p>/);
  const unconfigured = await markup(
    "/src/components/scanner/ScannerServiceStatus.jsx",
    { status: "unconfigured" },
  );
  assert.match(unconfigured, /Photo Preparation Only/);
  assert.doesNotMatch(unconfigured, /Retry Connection/);
  const panel = await markup(
    "/src/components/scanner/ScannerContinuePanel.jsx",
  );
  assert.equal((panel.match(/disabled=""/g) || []).length, 2);
  assert.doesNotMatch(panel, /<select|type="radio"|Play Against A Bot/);
});

test("scanner page leaves experimental labeling to the rulebook", async () => {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", {
    value: { location: { hostname: "localhost" } }, configurable: true,
  });
  try {
    const html = await markup("/src/pages/ScannerPage.jsx", {});
    assert.match(html, /AI Board Scanner/);
    assert.match(html, /Try on-device recognition/);
    assert.match(html, /Scanner Guide/);
    assert.match(html, /your prepared photo is sent to the server instead/);
    assert.doesNotMatch(html, /experimental/i);
    const hero = html.match(/<header class="scanner-hero">([\s\S]*?)<\/header>/)?.[1];
    assert.ok(hero, "Scanner retains one main header");
    assert.match(hero, /scanner-service-status/);
    assert.match(hero, /Recognition Options/);
    assert.match(hero, /Scanner progress/);
    assert.equal((html.match(/Recognition Options/g) || []).length, 1);
    assert.equal((html.match(/scanner-service-status/g) || []).length, 1);
  } finally {
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow);
    else delete globalThis.window;
  }
});

test("photo panel keeps essential guidance and collapses extra tips without decorative headings", async () => {
  const html = await markup("/src/components/scanner/ScannerPhotoPanel.jsx");
  assert.match(html, /Board Photo/);
  assert.match(html, /White&#x27;s home rank at the bottom/);
  assert.match(html, /Photos are sent only when you scan and are not stored/);
  assert.match(html, /<details class="ui-disclosure scanner-photo-tips">/);
  assert.match(html, /Photo Tips/);
  assert.doesNotMatch(html, /Your photograph|scanner-step-label|scanner-overline/);
});

test("scanner launch offers only local and online play and requires a reviewed valid position", async () => {
  const path = "/src/components/scanner/ScannerContinuePanel.jsx";
  const ready = {
    confirmed: true,
    remainingReviews: 0,
    validation: { valid: true, issues: [] },
  };
  const panel = await markup(path, ready);
  assert.match(panel, /Start Local Game/);
  assert.match(panel, /Create Online Game/);
  assert.doesNotMatch(panel, /Play Against A Bot|disabled=""/);
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
      2,
    );
  }
});

test("flagged squares label the current piece and provide one mark-correct action", async () => {
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
  assert.match(html, /\(Current Piece\)/);
  assert.equal((html.match(/Mark e5 Correct/g) || []).length, 1);
  assert.doesNotMatch(html, /Keep Current Piece/);
  assert.match(html, /Mark All Pieces Reviewed/);
});

test("current-piece markers follow the corrected board rather than original predictions", async () => {
  const board = Array.from({ length: 8 }, () => Array(8).fill(null));
  board[3][4] = { type: "rook", color: "black", name: "Rook" };
  const html = await markup("/src/components/scanner/ScannerBoardReview.jsx", {
    board, reviewSquares: [], selectedSquare: { row: 3, col: 4 },
    scan: { squareCandidates: [{ row: 3, col: 4, candidates: [{ class: "white-bishop", score: 0.8 }] }] },
  });
  assert.match(html, /Black rook<span class="scanner-current-label">\(Current Piece\)/);
  assert.equal((html.match(/\(Current Piece\)/g) || []).length, 1);
  assert.match(html, /No more squares to review/);
  assert.doesNotMatch(html, /Mark All Pieces Reviewed/);
  assert.match(html, /missing pieces, wrong pieces, and incorrect colors/);
  assert.match(html, /confirm all 64 squares below/);
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

test("home scanner card is same-tab and does not add a research product", async () => {
  const html = await markup("/src/components/scanner/ScannerFeatureCard.jsx");
  assert.match(html, /Continue Your Physical Game/);
  assert.match(html, /href="\/scanner"/);
  assert.doesNotMatch(html, /target="_blank"|Research|experimental/);
});

test("selected photo crops use logical board coordinates even for an empty square", async () => {
  const html = await markup("/src/components/scanner/ScannerBoardReview.jsx", {
    board: Array.from({ length: 8 }, () => Array(8).fill(null)),
    reviewSquares: [], selectedSquare: { row: 7, col: 7 }, photoUrl: "blob:prepared",
    scan: { squareCandidates: [] },
  });
  assert.match(html, /Photo crop of h1/);
  assert.match(html, /viewBox="7 7 1 1"/);
  assert.match(html, /href="blob:prepared"/);
});

test("scan details start collapsed and distinguish server wait from inference", async () => {
  const board = Array.from({ length: 8 }, () => Array(8).fill(null));
  const html = await markup("/src/components/scanner/ScannerScanDetails.jsx", {
    scan: { board, runtime: "onnx", inferenceMs: 100,
      clientTimings: { connectionMs: 1000, requestMs: 200, totalMs: 1200 } },
    board, reviewSquares: [], confirmed: false, showDetections: false,
  });
  assert.match(html, /Scan Details/);
  assert.match(html, /100 ms/);
  assert.match(html, /Connection \/ startup wait/);
  assert.match(html, /not measured probabilities/);
  assert.doesNotMatch(html, /<details[^>]* open|Review complete|Active review time/);
});

test("rulebook performance is collapsed and does not imply board accuracy or calibrated scores", async () => {
  const html = await markup("/src/components/scanner/ScannerPerformance.jsx");
  assert.match(html, /97\.95%/);
  assert.match(html, /This is not whole-board accuracy/);
  assert.match(html, /not yet measured/);
  assert.match(html, /89\.59%/);
  assert.match(html, /91\.47%/);
  assert.match(html, /1\.88%/);
  assert.match(html, /8\.53%/);
  assert.match(html, /149 extra detections/);
  assert.match(html, /6,283/);
  assert.match(html, /ResNet18/);
  assert.match(html, /intersection over union/);
  assert.match(html, /regression results, not a fresh test/);
  assert.match(html, /not calibrated probabilities/);
  assert.doesNotMatch(html, /<details[^>]* open/);
});
