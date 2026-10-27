const PIECE_CLASSES = new Set(
  ["white", "black"].flatMap((color) =>
    ["king", "queen", "rook", "bishop", "knight", "pawn"].map(
      (type) => `${color}-${type}`,
    ),
  ),
);

export function scannerServiceUrl(hostname, configured = "") {
  if (configured.trim()) return configured.trim().replace(/\/+$/, "");
  return ["localhost", "127.0.0.1"].includes(hostname)
    ? "http://127.0.0.1:8001"
    : "";
}

export async function scannerAvailability(url, signal, fetcher = fetch) {
  if (!url) return "unconfigured";
  try {
    const response = await fetcher(`${url}/health`, {
      signal,
      cache: "no-store",
    });
    if (!response.ok) return "offline";
    const health = await response.json();
    return health.ready === true ? "ready" : "offline";
  } catch (error) {
    if (error.name === "AbortError") throw error;
    return "offline";
  }
}

export function validateScanResponse(result) {
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
        !Number.isInteger(square.row) ||
        !Number.isInteger(square.col) ||
        square.row < 0 ||
        square.row > 7 ||
        square.col < 0 ||
        square.col > 7,
    )
  ) {
    throw new Error("The scanner returned an invalid board. Please retry.");
  }
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
