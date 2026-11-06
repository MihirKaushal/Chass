const PIECE_CLASSES = new Set(
  ["white", "black"].flatMap((color) =>
    ["king", "queen", "rook", "bishop", "knight", "pawn"].map(
      (type) => `${color}-${type}`,
    ),
  ),
);

export function scannerServiceUrl(
  hostname,
  configured = "",
  gameApi = "http://localhost:8000",
) {
  if (configured.trim()) return configured.trim().replace(/\/+$/, "");
  // Production photos go through the configured game API, never a visitor's localhost.
  if (
    !["localhost", "127.0.0.1"].includes(hostname) &&
    /^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(gameApi)
  )
    return "";
  return `${gameApi.replace(/\/+$/, "")}/scanner`;
}

export async function scannerAvailability(url, signal, fetcher = fetch) {
  if (!url) return "unconfigured";
  try {
    const response = await fetcher(`${url}/health`, {
      signal,
      cache: "no-store",
    });
    if (!response.ok)
      return [401, 403, 404].includes(response.status) ? "unavailable" : "offline";
    const health = await response.json();
    return health.configured === false
      ? "unconfigured"
      : health.ready === true
        ? "ready"
        : health.status === "unavailable"
          ? "unavailable"
          : "offline";
  } catch (error) {
    if (error.name === "AbortError") throw error;
    return "offline";
  }
}

function abortablePause(ms, signal) {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}

export async function waitForScanner(
  url,
  {
    signal,
    fetcher = fetch,
    onStatus = () => {},
    timeoutMs = 150000,
    retryDelayMs = 3000,
    attemptTimeoutMs = 45000,
  } = {},
) {
  signal?.throwIfAborted();
  if (!url) return "unconfigured";
  const connection = new AbortController();
  const cancel = () => connection.abort(signal.reason);
  signal?.addEventListener("abort", cancel, { once: true });
  const deadline = setTimeout(() => connection.abort(), timeoutMs);
  const notice = setTimeout(() => onStatus("warming"), 8000);
  onStatus("checking");
  try {
    // Retry health only, never an uploaded photo. Stop after the startup budget
    // rather than polling indefinitely and keeping a free service awake.
    while (!connection.signal.aborted) {
      const attempt = new AbortController();
      const stopAttempt = () => attempt.abort(connection.signal.reason);
      connection.signal.addEventListener("abort", stopAttempt, { once: true });
      const attemptTimer = setTimeout(() => attempt.abort(), attemptTimeoutMs);
      let status;
      try {
        status = await scannerAvailability(url, attempt.signal, fetcher);
      } catch (error) {
        if (error.name !== "AbortError") throw error;
        status = "offline";
      } finally {
        clearTimeout(attemptTimer);
        connection.signal.removeEventListener("abort", stopAttempt);
      }
      connection.signal.throwIfAborted();
      if (status === "ready" || status === "unconfigured") return status;
      if (status === "unavailable") return "offline";
      clearTimeout(notice);
      onStatus("warming");
      await abortablePause(retryDelayMs, connection.signal);
    }
    return "offline";
  } catch (error) {
    signal?.throwIfAborted();
    if (connection.signal.aborted) return "offline";
    throw error;
  } finally {
    clearTimeout(deadline);
    clearTimeout(notice);
    signal?.removeEventListener("abort", cancel);
  }
}

export function validateScanResponse(result) {
  const validSquare = (square) =>
    square &&
    Number.isInteger(square.row) &&
    Number.isInteger(square.col) &&
    square.row >= 0 &&
    square.row < 8 &&
    square.col >= 0 &&
    square.col < 8;
  if (
    !Array.isArray(result?.board) ||
    result.board.length !== 8 ||
    result.board.some(
      (row) =>
        !Array.isArray(row) ||
        row.length !== 8 ||
        row.some((piece) => piece !== null && !PIECE_CLASSES.has(piece)),
    ) ||
    !Array.isArray(result.reviewSquares) ||
    result.reviewSquares.some(
      (square) =>
        !validSquare(square) ||
        (square.reasons !== undefined &&
          (!Array.isArray(square.reasons) ||
            square.reasons.some((reason) => typeof reason !== "string"))),
    )
  ) {
    throw new Error("The scanner returned an invalid board. Please retry.");
  }
  if (
    (result.warnings !== undefined &&
      (!Array.isArray(result.warnings) ||
        result.warnings.some((warning) => typeof warning !== "string"))) ||
    result.reviewSquares.length > 64 ||
    (result.squareCandidates !== undefined &&
      (!Array.isArray(result.squareCandidates) ||
        result.squareCandidates.length > 64 ||
        result.squareCandidates.some(
          (square) =>
            !validSquare(square) ||
            !Array.isArray(square.candidates) ||
            square.candidates.length > 100 ||
            square.candidates.some(
              (candidate) =>
                !candidate ||
                !PIECE_CLASSES.has(candidate.class) ||
                (candidate.alternatives !== undefined &&
                  (!Array.isArray(candidate.alternatives) ||
                    candidate.alternatives.length > 12 ||
                    candidate.alternatives.some(
                      (option) =>
                        !option ||
                        !PIECE_CLASSES.has(option.label) ||
                        !Number.isFinite(option.score) ||
                        option.score < 0 ||
                        option.score > 1,
                    ))),
            ),
        )))
  )
    throw new Error(
      "The scanner returned invalid review suggestions. Please retry.",
    );
  return result;
}

export function reviewedBoardLabels(scan, board) {
  if (!/^[a-f0-9]{64}$/.test(scan?.imageSha256 || "")) {
    throw new Error(
      "Recognize the prepared photo before exporting its labels.",
    );
  }
  const labels = board.map((rank) =>
    rank.map((piece) => (piece ? `${piece.color}-${piece.type}` : null)),
  );
  validateScanResponse({ board: labels, reviewSquares: [] });
  return {
    format_version: 1,
    records: [
      {
        image_id: scan.imageSha256,
        image_sha256: scan.imageSha256,
        orientation: "white_bottom",
        verified: true,
        board: labels,
      },
    ],
  };
}

export function downloadScannerFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function recognizePhoto(url, file, signal, fetcher = fetch) {
  let response;
  try {
    response = await fetcher(`${url}/scan`, {
      method: "POST",
      headers: { "Content-Type": file.type || "image/jpeg" },
      body: file,
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "The scanner service is not reachable. Check the connection and try again.",
    );
  }
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(
      "The scanner returned an unreadable response. Please retry.",
    );
  }
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Recognition failed. Please retry.",
    );
  return validateScanResponse(result);
}
