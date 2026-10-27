import test from "node:test";
import assert from "node:assert/strict";
import {
  scannerServiceUrl,
  validateScanResponse,
  recognizePhoto,
  reviewedBoardLabels,
} from "./scannerApi.js";

test("reviewed labels retain the prepared photo hash and use all 64 edited squares", () => {
  const board = Array.from({ length: 8 }, () => Array(8).fill(null));
  board[7][4] = { type: "king", color: "white" };
  const result = reviewedBoardLabels({ imageSha256: "a".repeat(64) }, board);
  assert.equal(result.records[0].board[7][4], "white-king");
  assert.equal(result.records[0].orientation, "white_bottom");
  assert.equal(result.records[0].verified, true);
  assert.throws(() => reviewedBoardLabels({}, board), /Recognize/);
});

test("scanner does not silently send production photos to localhost", () => {
  assert.equal(scannerServiceUrl("playchass.vercel.app"), "");
  assert.equal(scannerServiceUrl("localhost"), "http://127.0.0.1:8001");
  assert.equal(
    scannerServiceUrl("localhost", " https://scanner.example/ "),
    "https://scanner.example",
  );
});

test("scanner validates the complete board and review coordinates", () => {
  const valid = {
    board: Array.from({ length: 8 }, () => Array(8).fill(null)),
    reviewSquares: [],
  };
  assert.equal(validateScanResponse(valid), valid);
  valid.board[0][0] = "black-king";
  assert.equal(validateScanResponse(valid), valid);
  valid.board[1][1] = "made-up-piece";
  assert.throws(() => validateScanResponse(valid), /invalid board/);
  valid.board[1][1] = null;
  valid.reviewSquares.push({ row: 8, col: 0 });
  assert.throws(() => validateScanResponse(valid), /invalid board/);
});

test("scanner handles unavailable service and preserves request cancellation", async () => {
  const file = new Blob(["photo"], { type: "image/png" });
  await assert.rejects(
    recognizePhoto("http://localhost", file, undefined, async () => {
      throw new TypeError("network");
    }),
    /not reachable/,
  );
  await assert.rejects(
    recognizePhoto("http://localhost", file, undefined, async () => {
      throw new DOMException("aborted", "AbortError");
    }),
    { name: "AbortError" },
  );
  await assert.rejects(
    recognizePhoto("http://localhost", file, undefined, async () => ({
      ok: false,
      json: async () => ({ detail: "Models not loaded" }),
    })),
    /Models not loaded/,
  );
});
