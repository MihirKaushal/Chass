import assert from "node:assert/strict";
import test from "node:test";
import {
  defaultScannerDetails,
  pieceFromLabel,
  scannerDetailError,
  scannerImportPayload,
  squareAlternatives,
} from "./scannerReview.js";

test("scanner uses conservative optional history defaults and serializes corrected squares", () => {
  const details = defaultScannerDetails();
  assert.equal(details.enPassant, null);
  assert.equal(Object.values(details.castlingRights).some(Boolean), false);
  const board = Array.from({ length: 8 }, () => Array(8).fill(null));
  board[7][4] = { type: "king", color: "white" };
  const payload = scannerImportPayload(
    board,
    {
      ...details,
      currentPlayer: "black",
      halfmoveClock: "",
      fullmoveNumber: "23",
    },
    { mode: "online", confirmed: true },
  );
  assert.equal(payload.board[7][4], "white-king");
  assert.equal(payload.halfmoveClock, 0);
  assert.equal(payload.fullmoveNumber, 23);
  assert.equal(payload.currentPlayer, "black");
  assert.equal(payload.mode, "online");
  assert.equal(payload.reviewConfirmed, true);
  assert.equal(scannerDetailError(details), "");
  for (const value of [-1, 100, 1.5, "invalid"])
    assert.notEqual(
      scannerDetailError({ ...details, halfmoveClock: value }),
      "",
    );
});

test("uncertain candidates combine competing detections and rank unique legal pieces", () => {
  const scan = {
    squareCandidates: [
      {
        row: 2,
        col: 3,
        candidates: [
          {
            class: "black-bishop",
            classifierScore: 0.51,
            alternatives: [
              { label: "black-queen", score: 0.4 },
              { label: "black-king", score: 0.09 },
            ],
          },
          {
            class: "black-queen",
            classifierScore: 0.6,
            alternatives: [{ label: "black-elephant", score: 0.9 }],
          },
        ],
      },
    ],
  };
  assert.deepEqual(
    squareAlternatives(scan, { row: 2, col: 3 }).map(({ label }) => label),
    ["black-queen", "black-bishop", "black-king"],
  );
  assert.deepEqual(squareAlternatives(scan, { row: 0, col: 0 }), []);
  assert.equal(pieceFromLabel("white-king-bad"), null);
  assert.equal(pieceFromLabel("neutral-king"), null);
});
