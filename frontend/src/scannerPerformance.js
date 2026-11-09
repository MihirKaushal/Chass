// Frozen box-level benchmark snapshots; regression tests check these against the source reports.
export const SCANNER_PERFORMANCE = {
  recordedOn: "November 6, 2026",
  photos: 338,
  pieces: 6283,
  history: [
    { name: "Detector only", correct: 3082, located: 5561 },
    { name: "Crop classifier", correct: 5342, located: 5546 },
    { name: "King-focused update", correct: 5629, located: 5747 },
  ],
  missed: 536,
  extra: 149,
  correctAll: 5629,
};
