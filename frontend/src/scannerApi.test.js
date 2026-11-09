import test from "node:test";
import assert from "node:assert/strict";
import {
  scannerServiceUrl,
  validateScanResponse,
  recognizePhoto,
  reviewedBoardLabels,
  scannerAvailability,
  waitForScanner,
} from "./scannerApi.js";

test("scanner availability distinguishes missing setup, loaded models and offline service", async () => {
  let requests = 0;
  const ready = async () => {
    requests += 1;
    return { ok: true, json: async () => ({ ready: true }) };
  };
  assert.equal(await scannerAvailability("", undefined, ready), "unconfigured");
  assert.equal(requests, 0);
  assert.equal(
    await scannerAvailability("http://localhost:8001", undefined, ready),
    "ready",
  );
  assert.equal(
    await scannerAvailability("local", undefined, async () => ({
      ok: true,
      json: async () => ({ ready: false }),
    })),
    "offline",
  );
  assert.equal(
    await scannerAvailability("local", undefined, async () => ({ ok: false })),
    "offline",
  );
  assert.equal(
    await scannerAvailability("local", undefined, async () => {
      throw new TypeError("network");
    }),
    "offline",
  );
  await assert.rejects(
    scannerAvailability("local", undefined, async () => {
      throw new DOMException("cancel", "AbortError");
    }),
    { name: "AbortError" },
  );
});

const flush = () => new Promise((resolve) => setImmediate(resolve));
const healthResponse = (body) => ({ ok: true, json: async () => body });

test("connection automatically recovers from cold-host HTML and legacy not-ready responses", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const states = [];
  let requests = 0;
  const result = waitForScanner("https://api.example/scanner", {
    onStatus: (state) => states.push(state),
    fetcher: async (url, options) => {
      requests += 1;
      assert.equal(url, "https://api.example/scanner/health");
      assert.equal(options.cache, "no-store");
      assert.equal(options.method, undefined);
      if (requests === 1) return { ok: true, json: async () => { throw new SyntaxError("HTML waking page"); } };
      return healthResponse({ ready: requests >= 3, configured: true });
    },
  });
  await flush();
  assert.equal(requests, 1);
  assert.deepEqual(states, ["checking", "warming"]);
  t.mock.timers.tick(3000);
  await flush();
  t.mock.timers.tick(3000);
  assert.equal(await result, "ready");
  t.mock.timers.tick(200000);
  await flush();
  assert.equal(requests, 3, "no background keep-alive after connection");
});

test("readiness retries network errors and transient HTTP responses", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let requests = 0;
  const result = waitForScanner("test", {
    fetcher: async () => {
      requests += 1;
      if (requests === 1) throw new TypeError("network");
      if (requests === 2) return { ok: false, status: 503 };
      return healthResponse({ ready: true });
    },
  });
  await flush();
  t.mock.timers.tick(3000);
  await flush();
  t.mock.timers.tick(3000);
  assert.equal(await result, "ready");
});

test("an individual hung probe is cancelled and retried within the overall budget", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let requests = 0;
  const states = [];
  const result = waitForScanner("test", {
    onStatus: (state) => states.push(state),
    fetcher: async (_, { signal }) => {
      requests += 1;
      if (requests > 1) return healthResponse({ ready: true });
      return new Promise((_, reject) => {
        signal.addEventListener("abort", () => reject(signal.reason), { once: true });
      });
    },
  });
  t.mock.timers.tick(8000);
  assert.equal(states.at(-1), "warming");
  t.mock.timers.tick(37000);
  await flush();
  t.mock.timers.tick(3000);
  assert.equal(await result, "ready");
});

test("readiness stops at its deadline and preserves cancellation on navigation", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let requests = 0;
  const fetcher = async () => { requests += 1; return healthResponse({ ready: false }); };
  const expired = waitForScanner("test", { fetcher });
  await flush();
  t.mock.timers.tick(150000);
  assert.equal(await expired, "offline");
  assert.equal(requests, 1);
  const controller = new AbortController();
  const cancelled = waitForScanner("test", { signal: controller.signal, fetcher });
  const rejection = assert.rejects(cancelled, { name: "AbortError" });
  await flush();
  controller.abort();
  await rejection;
  t.mock.timers.tick(200000);
  assert.equal(requests, 2);
  await assert.rejects(waitForScanner("test", { signal: controller.signal, fetcher }), { name: "AbortError" });
  assert.equal(requests, 2);
});

test("cancelling an active probe aborts its fetch and ignores a late success", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const controller = new AbortController();
  let attemptSignal;
  let resolveFetch;
  const result = waitForScanner("test", {
    signal: controller.signal,
    fetcher: (_, { signal }) => {
      attemptSignal = signal;
      return new Promise((resolve) => { resolveFetch = resolve; });
    },
  });
  const rejection = assert.rejects(result, { name: "AbortError" });
  controller.abort();
  assert.equal(attemptSignal.aborted, true);
  resolveFetch(healthResponse({ ready: true }));
  await rejection;
});

test("missing setup and permanent configuration failures do not retry endlessly", async () => {
  for (const [response, expected] of [
    [healthResponse({ ready: false, configured: false }), "unconfigured"],
    [healthResponse({ ready: false, status: "unavailable" }), "offline"],
    [{ ok: false, status: 401 }, "offline"],
  ]) {
    let requests = 0;
    assert.equal(await waitForScanner("test", {
      fetcher: async () => { requests += 1; return response; },
    }), expected);
    assert.equal(requests, 1);
  }
  assert.equal(await waitForScanner("", { fetcher: () => assert.fail("no URL") }), "unconfigured");
});

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
  assert.equal(scannerServiceUrl("localhost"), "http://localhost:8000/scanner");
  assert.equal(
    scannerServiceUrl("playchass.vercel.app", "", "https://game.example"),
    "https://game.example/scanner",
  );
  assert.equal(
    scannerServiceUrl("localhost", " https://scanner.example/ "),
    "https://scanner.example",
  );
});

test("unconfigured proxy and malformed candidate payloads fail safely", async () => {
  assert.equal(
    await scannerAvailability(
      "https://game.example/scanner",
      undefined,
      async () => ({
        ok: true,
        json: async () => ({ configured: false, ready: false }),
      }),
    ),
    "unconfigured",
  );
  const base = {
    board: Array.from({ length: 8 }, () => Array(8).fill(null)),
    reviewSquares: [],
  };
  assert.throws(
    () => validateScanResponse({ ...base, squareCandidates: "bad" }),
    /invalid review/,
  );
  assert.throws(
    () =>
      validateScanResponse({
        ...base,
        squareCandidates: [{ row: 0, col: 0, candidates: [null] }],
      }),
    /invalid review/,
  );
  assert.throws(
    () => validateScanResponse({ ...base, reviewSquares: [null] }),
    /invalid board/,
  );
  assert.throws(
    () => validateScanResponse({ ...base, warnings: [{}] }),
    /invalid review/,
  );
  assert.throws(
    () =>
      validateScanResponse({
        ...base,
        squareCandidates: [
          {
            row: 0,
            col: 0,
            candidates: [{ class: "white-pawn", alternatives: [null] }],
          },
        ],
      }),
    /invalid review/,
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
