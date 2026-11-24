// Lichess opens a FEN in its analysis board when spaces become underscores.
export function lichessAnalysisUrl(fen) {
  if (!fen) return null;
  const path = fen.trim().split(/\s+/).map(encodeURI).join("_");
  return `https://lichess.org/analysis/standard/${path}`;
}
