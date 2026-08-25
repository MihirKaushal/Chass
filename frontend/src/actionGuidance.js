import { actionsForGlobalSelection } from "./specialActionSelection.js";

const ACTION_COPY = {
  catapult_projectile: {
    title: "Catapult projectile ready",
    instruction: "Choose a red target. The Catapult stays in place and begins recovery.",
  },
  move_barricade: {
    title: "Barricade movement ready",
    instruction: "Choose a teal target to reposition the controlled wall.",
  },
  demolish_barricade: {
    title: "Rook sacrifice ready",
    instruction: "Choose a red Barricade target. The Rook and wall will both be removed.",
  },
  getaway: {
    title: "Getaway ready",
    instruction: "Choose the gold Queen target to complete the emergency swap.",
  },
  episcopal: {
    title: "Episcopal shift ready",
    instruction: "Choose a gold target to move the Bishop onto the opposite square color.",
  },
  eye_for_an_eye: {
    title: "Eye for an Eye ready",
    instruction: "Choose the red matching enemy piece to complete the trade.",
  },
  necromancy: {
    title: "Necromancy ready",
    instruction: "Choose a green home square to return the selected captured piece.",
  },
  scorch: {
    title: "Scorch ready",
    instruction: "Choose an ember target. That square becomes permanently impassable.",
  },
};

const POWER_COPY = {
  reinforce: {
    title: "Reinforce command ready",
    description: "Spend one command point to deploy a Pawn.",
    instruction: "Choose one of the pulsing home-row squares.",
  },
  evolve: {
    title: "Evolve command ready",
    description: "Spend two command points to upgrade a Pawn.",
    instruction: "Choose one of the pulsing Pawns after selecting Knight or Bishop.",
  },
  stronghold: {
    title: "Stronghold command ready",
    description: "Spend three command points to deploy a Rook.",
    instruction: "Choose one of the pulsing first-three-rank squares.",
  },
};

function pieceAt(game, square) {
  if (!square) return null;
  return game.board?.[square.row]?.[square.col] || null;
}

function sourceMoveCount(game, square) {
  if (!square) return 0;
  return (game.validMoves || []).filter(
    (move) => move.from.row === square.row && move.from.col === square.col
  ).length;
}

function actionGuidance(actions, game, source) {
  const action = actions[0];
  const copy = ACTION_COPY[action.actionType] || {
    title: `${action.label} ready`,
    instruction: "Choose one of the marked board targets.",
  };
  const piece = pieceAt(game, source);
  const capturedPiece = action.actionType === "necromancy"
    ? game.capturedPieces?.[action.owner]?.find(
        (candidate) => candidate.pieceId === action.params?.capturedPieceId
      )
    : null;
  const description = capturedPiece
    ? `${capturedPiece.name} costs ${capturedPiece.points ?? 0} point${capturedPiece.points === 1 ? "" : "s"} and has ${actions.length} legal home square${actions.length === 1 ? "" : "s"}.`
    : piece
      ? `${piece.name} has ${actions.length} legal special target${actions.length === 1 ? "" : "s"}.`
      : action.description;
  return {
    state: "action",
    marker: action.boardMarker || "ability",
    icon: action.icon || "✦",
    title: copy.title,
    description,
    instruction: copy.instruction,
  };
}

export function buildActionGuidance({
  game,
  selectedSquare,
  selectedBoardAction,
  selectedPower,
  selectedGlobalActionKey,
  powerTargets = [],
}) {
  if (selectedGlobalActionKey) {
    const actions = actionsForGlobalSelection(
      game.availableActions || [],
      selectedGlobalActionKey
    );
    if (actions.length) return actionGuidance(actions, game, null);
  }

  if (selectedPower) {
    const copy = POWER_COPY[selectedPower] || {
      title: "Command action ready",
      description: "Spend command points to alter the board.",
      instruction: "Choose one of the pulsing board targets.",
    };
    return {
      state: "power",
      marker: "ability",
      icon: "✦",
      ...copy,
      description: `${copy.description} ${powerTargets.length} legal target${powerTargets.length === 1 ? "" : "s"}.`,
    };
  }

  if (selectedBoardAction?.actions?.length) {
    return actionGuidance(
      selectedBoardAction.actions,
      game,
      selectedBoardAction.source
    );
  }

  const piece = pieceAt(game, selectedSquare);
  if (piece) {
    const moveCount = sourceMoveCount(game, selectedSquare);
    return {
      state: "piece",
      marker: "standard",
      icon: "",
      title: `${piece.name} selected`,
      description: piece.isCustom
        ? piece.movement || piece.description
        : `${moveCount} legal move${moveCount === 1 ? "" : "s"} available.`,
      instruction: moveCount
        ? "Choose a blue target, select another piece, or tap this piece again to cancel."
        : "This piece has no legal move right now. Select another piece to continue.",
    };
  }

  return {
    state: "idle",
    marker: null,
    icon: null,
    title: `${game.currentPlayer === "black" ? "Black" : "White"} to move`,
    description: "Select a piece or choose an available special action.",
    instruction: "Board guidance will update before you commit an action.",
  };
}
