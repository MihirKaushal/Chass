// Frozen box-level benchmark snapshots; regression tests check these against the source reports.
export const SCANNER_PERFORMANCE = {
  recordedOn: "November 8, 2026",
  photos: 355,
  pieces: 6376,
  located: 5855,
  historyPhotos: 338,
  historyPieces: 6283,
  history: [
    { name: "Detector only", correct: 3082, located: 5561 },
    { name: "Crop classifier", correct: 5342, located: 5546 },
    { name: "King-focused update", correct: 5629, located: 5747 },
    { name: "Combined-data update", correct: 5641, located: 5769 },
  ],
  sources: [
    { key: "chess-v2", name: "Chess V2", photos: 338, pieces: 6283, previous: 5629, correct: 5641 },
    { key: "top-down", name: "Chess Top Down", photos: 17, pieces: 93, previous: 50, correct: 80 },
  ],
  sourceBalancedF1: 0.895758921138798,
  missed: 521,
  extra: 129,
  correctAll: 5721,
};
