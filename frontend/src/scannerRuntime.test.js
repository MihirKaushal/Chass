import test from "node:test";
import assert from "node:assert/strict";
import { scannerWakeUrl, waitForScanner, addKingReviewHints } from "./scannerApi.js";
import { recognizeInBrowser, recognizeWithFallback } from "./scanner/browserClient.js";
import { roundEven, suppress, assembleBoard } from "./scanner/browserMath.js";

const board = () => Array.from({ length: 8 }, () => Array(8).fill(null));

test("parallel startup never sends credentials or treats public readiness as authorized readiness", async () => {
  const calls = [];
  const wakeUrl = scannerWakeUrl("https://chass-api.onrender.com/scanner");
  const result = await waitForScanner("https://game.example/scanner", {
    wakeUrl, retryDelayMs: 1,
    fetcher: async (url, options) => {
      calls.push({ url, options });
      if (url === wakeUrl) return { ok: true, json: async () => ({ ready: true }) };
      assert.equal(calls[0].url, wakeUrl);
      return { ok: false, status: 401 };
    },
  });
  assert.equal(result, "offline");
  assert.equal(calls.length, 2);
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(calls[0].options.signal.aborted, true);
  for (const invalid of ["https://secret@host/ready", "https://host/scan", "https://host/ready?token=x", "http://public/ready"])
    assert.equal(scannerWakeUrl("", invalid), "");
});

test("king hints flag plausible corrections without fabricating or replacing pieces", () => {
  const result = { board: board(), reviewSquares: [], squareCandidates: [{ row: 0, col: 3,
    candidates: [{ class: "black-pawn", alternatives: [{ label: "black-king", score: .2 }] }] }] };
  result.board[0][3] = "black-pawn";
  result.board[7][4] = "white-king";
  const fixed = addKingReviewHints(result);
  assert.deepEqual(fixed.board, result.board);
  assert.equal(fixed.reviewSquares.length, 1);
  assert.match(fixed.warnings[0], /Black King not found/);
  assert.equal(result.reviewSquares.length, 0);
  result.board[0][3] = result.board[1][2] = "black-king";
  assert.equal(addKingReviewHints(result).reviewSquares.length, 2);
});

test("browser failure falls back once but cancellation never uploads a photo", async () => {
  let uploads = 0;
  const controller = new AbortController();
  const args = { enabled: true, signal: controller.signal, onStatus: () => {},
    browser: async () => { throw new Error("GPU unavailable"); }, server: async () => ++uploads };
  assert.equal(await recognizeWithFallback(args), 1);
  controller.abort();
  await assert.rejects(recognizeWithFallback(args), { name: "AbortError" });
  assert.equal(uploads, 1);
  assert.equal(await recognizeWithFallback({ ...args, signal: new AbortController().signal,
    browser: async () => "local" }), "local");
  assert.equal(uploads, 1);
});

test("browser worker terminates on success, malformed response, timeout and abort", async () => {
  let terminated;
  let worker;
  const factory = () => (worker = { terminate: () => { terminated = true; }, postMessage: () => {} });
  let promise = recognizeInBrowser(new Blob(), undefined, () => {}, { workerFactory: factory });
  worker.onmessage({ data: { result: { board: board(), reviewSquares: [] } } });
  assert.equal((await promise).board.length, 8);
  assert.equal(terminated, true);
  terminated = false;
  promise = recognizeInBrowser(new Blob(), undefined, () => {}, { workerFactory: factory });
  worker.onmessage({ data: { result: {} } });
  await assert.rejects(promise, /invalid board/);
  assert.equal(terminated, true);
  promise = recognizeInBrowser(new Blob(), undefined, () => {}, { workerFactory: factory, timeoutMs: 5 });
  await assert.rejects(promise, /timed out/);
  const controller = new AbortController();
  promise = recognizeInBrowser(new Blob(), controller.signal, () => {}, { workerFactory: factory });
  controller.abort();
  await assert.rejects(promise, { name: "AbortError" });
});

test("browser decoding keeps deterministic rounding, duplicate suppression and review geometry", () => {
  assert.deepEqual([.5, 1.5, 2.5, 3.5].map(roundEven), [0, 2, 2, 4]);
  const proposals = [{ box: [0, 0, 10, 10], score: .9 }, { box: [0, 0, 10, 10], score: .8 }];
  assert.equal(suppress(proposals, .4, true).length, 1);
  const result = assembleBoard([{ box: [20, 20, 80, 80], class: "white-king", classifierScore: .6,
    score: .8, alternatives: [] }], 800, 800);
  assert.equal(result.board[0][0], "white-king");
  assert.equal(result.reviewSquares[0].label, "a8");
});
