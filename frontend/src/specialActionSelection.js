const NECROMANCY_PREFIX = "necromancy:";

export function globalActionSelectionKey(action) {
  if (!action?.actionType || action.source) return null;
  if (action.actionType !== "necromancy") return action.actionType;

  const capturedPieceId = action.params?.capturedPieceId;
  return capturedPieceId ? `${NECROMANCY_PREFIX}${capturedPieceId}` : "necromancy";
}

export function actionsForGlobalSelection(actions = [], selectionKey = null) {
  if (!selectionKey) return [];
  return actions.filter(
    (action) => !action.source && globalActionSelectionKey(action) === selectionKey
  );
}

export function boardActionsWithStandardMovePriority(
  actions = [],
  standardTargetKeys = new Set()
) {
  return actions.filter((action) => (
    action.actionType !== "eye_for_an_eye"
    || !action.target
    || !standardTargetKeys.has(`${action.target.row}-${action.target.col}`)
  ));
}

export function necromancyPurchaseOptions(actions = [], capturedPieces = []) {
  const capturedById = new Map(
    capturedPieces.map((piece) => [piece.pieceId, piece])
  );
  const grouped = new Map();

  actions.forEach((action) => {
    if (action.actionType !== "necromancy") return;
    const capturedPieceId = action.params?.capturedPieceId;
    if (!capturedPieceId) return;

    if (!grouped.has(capturedPieceId)) {
      const captured = capturedById.get(capturedPieceId);
      grouped.set(capturedPieceId, {
        capturedPieceId,
        selectionKey: globalActionSelectionKey(action),
        piece: captured || {
          pieceId: capturedPieceId,
          type: "unknown",
          name: action.label?.replace(/^Recruit\s+/, "") || "Captured Piece",
          color: action.owner,
          points: 0,
          symbol: action.icon || "☠",
        },
        actions: [],
      });
    }
    grouped.get(capturedPieceId).actions.push(action);
  });

  return [...grouped.values()].map((option) => ({
    ...option,
    cost: option.piece.points ?? 0,
    targetCount: option.actions.length,
  }));
}
