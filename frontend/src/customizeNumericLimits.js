const FALLBACK_LIMITS = Object.freeze({
  boardMin: 4,
  boardMax: 16,
  pointMin: 0,
  pointMax: 100000,
  timeSecondsMin: 60,
  timeSecondsMax: 86400,
  targetPointsMin: 1,
  targetPointsMax: 100000,
  dominionRoundsMin: 1,
  dominionRoundsMax: 20,
  checkTargetMin: 1,
  checkTargetMax: 100,
  commandPointCapMin: 1,
  commandPointCapMax: 20,
  affinitySquareCountMin: 2,
  affinitySquareCountMax: 32,
  affinityControlRequiredMin: 1,
  affinityControlRequiredMax: 16,
  abilitySelectionMin: 1,
  abilitySelectionMax: 16,
  barricadeCountMin: 0,
  barricadeCountMax: 8,
  gambitBudgetMin: 0,
  gambitBudgetMax: 100000,
  gambitMaxPiecesMin: 1,
  gambitMaxPiecesMax: 128,
  gambitSetupRowsMin: 1,
  gambitSetupRowsMax: 8,
  gambitMaxQueensMin: 0,
  gambitMaxQueensMax: 32,
  pieceCapMin: 0,
  draftPoolCountMin: 0,
  draftPoolCountMax: 256,
});

function resolvedLimits(supplied = {}) {
  return { ...FALLBACK_LIMITS, ...supplied };
}

export function clampWholeNumber(value, minimum, maximum) {
  const safeMinimum = Math.trunc(Number(minimum));
  const safeMaximum = Math.max(safeMinimum, Math.trunc(Number(maximum)));
  const number = Number(value);
  if (!Number.isFinite(number)) return safeMinimum;
  return Math.max(safeMinimum, Math.min(safeMaximum, Math.trunc(number)));
}

export function clampEvenWholeNumber(value, minimum, maximum) {
  const clamped = clampWholeNumber(value, minimum, maximum);
  const even = clamped - (clamped % 2);
  return Math.max(minimum, Math.min(maximum, even));
}

export function customizeNumericBounds(draft = {}, suppliedLimits = {}) {
  const limits = resolvedLimits(suppliedLimits);
  const boardRows = clampWholeNumber(
    draft.boardRows ?? 8,
    limits.boardMin,
    limits.boardMax
  );
  const boardCols = clampWholeNumber(
    draft.boardCols ?? 8,
    limits.boardMin,
    limits.boardMax
  );
  const setupRowsMaximum = Math.max(
    limits.gambitSetupRowsMin,
    Math.min(limits.gambitSetupRowsMax, Math.floor(boardRows / 2))
  );
  const setupRows = clampWholeNumber(
    draft.gambit?.setupRows ?? 2,
    limits.gambitSetupRowsMin,
    setupRowsMaximum
  );
  const maxPiecesMaximum = Math.max(
    limits.gambitMaxPiecesMin,
    Math.min(limits.gambitMaxPiecesMax, setupRows * boardCols)
  );
  const maxPieces = clampWholeNumber(
    draft.gambit?.maxPieces ?? 16,
    limits.gambitMaxPiecesMin,
    maxPiecesMaximum
  );
  const maxQueensMaximum = Math.max(
    limits.gambitMaxQueensMin,
    Math.min(limits.gambitMaxQueensMax, maxPieces - 1)
  );
  const enabledAbilityCount = new Set(draft.specialAbilities?.allowed || []).size;
  const abilityCountMaximum = Math.max(
    limits.abilitySelectionMin,
    Math.min(limits.abilitySelectionMax, enabledAbilityCount)
  );
  const barricadeEnabled = (draft.enabledPieces || []).includes("barricade");
  const barricadeCountMinimum = barricadeEnabled ? 1 : limits.barricadeCountMin;
  const barricadeCountMaximum = Math.max(
    barricadeCountMinimum,
    Math.min(limits.barricadeCountMax, Math.floor(boardCols / 2))
  );
  const kingPoints = clampWholeNumber(
    draft.pointValues?.king ?? 0,
    limits.pointMin,
    limits.pointMax
  );
  const affinitySquareCountMaximum = Math.max(
    limits.affinitySquareCountMin,
    Math.min(limits.affinitySquareCountMax, boardCols * 2)
  );
  const affinitySquareCount = clampEvenWholeNumber(
    draft.customRules?.affinitySquareCount ?? 4,
    limits.affinitySquareCountMin,
    affinitySquareCountMaximum
  );
  const affinityControlRequiredMaximum = Math.max(
    limits.affinityControlRequiredMin,
    Math.min(
      limits.affinityControlRequiredMax,
      affinitySquareCount / 2
    )
  );

  return {
    ...limits,
    timeMinutesMin: Math.ceil(limits.timeSecondsMin / 60),
    timeMinutesMax: Math.floor(limits.timeSecondsMax / 60),
    abilityCountMaximum,
    barricadeCountMinimum,
    barricadeCountMaximum,
    affinitySquareCountMaximum,
    affinityControlRequiredMaximum,
    gambitBudgetMinimum: Math.max(limits.gambitBudgetMin, kingPoints),
    gambitSetupRowsMaximum: setupRowsMaximum,
    gambitMaxPiecesMaximum: maxPiecesMaximum,
    gambitMaxQueensMaximum: maxQueensMaximum,
    pieceCapMaximum: maxPieces,
    draftPoolCountMaximum: Math.min(
      limits.draftPoolCountMax,
      maxPieces * 2
    ),
  };
}

function boundedRecord(values, minimum, maximum) {
  return Object.fromEntries(
    Object.entries(values || {}).map(([key, value]) => [
      key,
      clampWholeNumber(value, minimum, maximum),
    ])
  );
}

export function normalizeCustomizeNumbers(draft, suppliedLimits = {}) {
  if (!draft) return draft;
  const limits = resolvedLimits(suppliedLimits);
  const initialBounds = customizeNumericBounds(draft, limits);
  const boardRows = clampWholeNumber(draft.boardRows, limits.boardMin, limits.boardMax);
  const boardCols = clampWholeNumber(draft.boardCols, limits.boardMin, limits.boardMax);
  const pointValues = boundedRecord(draft.pointValues, limits.pointMin, limits.pointMax);
  const kingPoints = pointValues.king ?? limits.pointMin;
  const setupRows = clampWholeNumber(
    draft.gambit?.setupRows,
    limits.gambitSetupRowsMin,
    initialBounds.gambitSetupRowsMaximum
  );
  const maxPieces = clampWholeNumber(
    draft.gambit?.maxPieces,
    limits.gambitMaxPiecesMin,
    initialBounds.gambitMaxPiecesMaximum
  );
  const maxQueensMaximum = Math.max(
    limits.gambitMaxQueensMin,
    Math.min(limits.gambitMaxQueensMax, maxPieces - 1)
  );
  const maxQueens = clampWholeNumber(
    draft.gambit?.maxQueens,
    limits.gambitMaxQueensMin,
    maxQueensMaximum
  );
  const draftPoolMaximum = Math.min(limits.draftPoolCountMax, maxPieces * 2);
  const pieceCaps = boundedRecord(
    draft.pieceCaps,
    limits.pieceCapMin,
    maxPieces
  );
  const draftPool = boundedRecord(
    draft.gambit?.draftPool,
    limits.draftPoolCountMin,
    draftPoolMaximum
  );
  pieceCaps.king = 1;
  pieceCaps.queen = maxQueens;
  draftPool.king = 2;
  const affinitySquareCount = clampEvenWholeNumber(
    draft.customRules?.affinitySquareCount ?? 4,
    limits.affinitySquareCountMin,
    initialBounds.affinitySquareCountMaximum
  );

  return {
    ...draft,
    boardRows,
    boardCols,
    barricadeCount: clampWholeNumber(
      draft.barricadeCount,
      initialBounds.barricadeCountMinimum,
      initialBounds.barricadeCountMaximum
    ),
    pointValues,
    pieceCaps,
    victory: {
      ...draft.victory,
      targetPoints: clampWholeNumber(
        draft.victory?.targetPoints,
        limits.targetPointsMin,
        limits.targetPointsMax
      ),
      timeSeconds: clampWholeNumber(
        draft.victory?.timeSeconds,
        limits.timeSecondsMin,
        limits.timeSecondsMax
      ),
      kingPoints,
      dominionRounds: clampWholeNumber(
        draft.victory?.dominionRounds,
        limits.dominionRoundsMin,
        limits.dominionRoundsMax
      ),
      checkTarget: clampWholeNumber(
        draft.victory?.checkTarget,
        limits.checkTargetMin,
        limits.checkTargetMax
      ),
    },
    customRules: {
      ...draft.customRules,
      affinitySquareCount,
      affinityControlRequired: clampWholeNumber(
        draft.customRules?.affinityControlRequired ?? 2,
        limits.affinityControlRequiredMin,
        Math.min(
          limits.affinityControlRequiredMax,
          affinitySquareCount / 2
        )
      ),
      commandPointCap: clampWholeNumber(
        draft.customRules?.commandPointCap,
        limits.commandPointCapMin,
        limits.commandPointCapMax
      ),
    },
    specialAbilities: {
      ...draft.specialAbilities,
      maxPerPlayer: clampWholeNumber(
        draft.specialAbilities?.maxPerPlayer,
        limits.abilitySelectionMin,
        initialBounds.abilityCountMaximum
      ),
    },
    gambit: {
      ...draft.gambit,
      budget: clampWholeNumber(
        draft.gambit?.budget,
        Math.max(limits.gambitBudgetMin, kingPoints),
        limits.gambitBudgetMax
      ),
      maxPieces,
      setupRows,
      maxQueens,
      draftPool,
    },
  };
}
