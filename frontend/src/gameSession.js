const SESSION_PREFIX = "chass:game:";
const memorySessions = new Map();


function storageKey(gameId) {
  return `${SESSION_PREFIX}${gameId}`;
}

export function saveGameSession(gameId, session) {
  const normalized = {
    gameId,
    mode: session.mode,
    variant: session.variant || "classic",
    token: session.token || null,
    color: session.color || null,
    role: session.role,
    inviteToken: session.inviteToken || null,
    inviteCode: session.inviteCode || null,
    inviteUrl: session.inviteUrl || null,
    inviteExpiresAt: session.inviteExpiresAt || null,
  };
  const serialized = JSON.stringify(normalized);
  memorySessions.set(gameId, normalized);

  try {
    localStorage.setItem(storageKey(gameId), serialized);
  } catch {
    try {
      sessionStorage.setItem(storageKey(gameId), serialized);
    } catch {
      // In-memory storage still supports navigation during this page lifetime.
    }
  }
}

export function loadGameSession(gameId) {
  const inMemory = memorySessions.get(gameId);
  if (inMemory) {
    return inMemory;
  }

  try {
    const value =
      localStorage.getItem(storageKey(gameId)) || sessionStorage.getItem(storageKey(gameId));
    if (!value) {
      return null;
    }
    const parsed = JSON.parse(value);
    memorySessions.set(gameId, parsed);
    return parsed;
  } catch {
    return null;
  }
}

export function updateGameSession(gameId, patch) {
  const current = loadGameSession(gameId) || { gameId };
  const updated = { ...current, ...patch };
  saveGameSession(gameId, updated);
  return updated;
}

export function createInviteUrl(inviteToken) {
  return `${window.location.origin}/join/${encodeURIComponent(inviteToken)}`;
}

export function playerHasAbility(game, color, abilityId) {
  const selected = game?.abilities?.selected?.[color];
  if (Array.isArray(selected)) {
    return selected.includes(abilityId);
  }
  return selected === abilityId;
}

export function mergeHistoryRecords(...groups) {
  const records = new Map();
  groups.flat().forEach((record) => {
    if (record?.moveNumber != null) {
      records.set(record.moveNumber, record);
    }
  });
  return [...records.values()].sort((left, right) => left.moveNumber - right.moveNumber);
}

export function projectPendingMove(game, move, promotion = null) {
  if (!game?.board || !move?.from || !move?.to) return game;

  const board = game.board.map((row) => [...row]);
  const movingPiece = board[move.from.row]?.[move.from.col];
  if (!movingPiece || !board[move.to.row]) return game;

  for (const capture of move.captures || []) {
    if (board[capture.row]?.[capture.col] !== undefined) {
      board[capture.row][capture.col] = null;
    }
  }
  board[move.from.row][move.from.col] = null;

  if (promotion === "kamikaze") {
    board[move.to.row][move.to.col] = null;
  } else {
    const promotedDefinition = promotion
      ? game.pieceDefinitions?.find((definition) => definition.type === promotion)
      : null;
    board[move.to.row][move.to.col] = {
      ...movingPiece,
      ...(promotedDefinition
        ? {
            type: promotedDefinition.type,
            name: promotedDefinition.name,
            points: promotedDefinition.points,
            symbol: promotedDefinition.symbols?.[movingPiece.color] || promotedDefinition.icon,
            icon: promotedDefinition.icon,
            description: promotedDefinition.description,
            movement: promotedDefinition.movement,
            customAttributes: promotedDefinition.customAttributes || {},
            isCustom: promotedDefinition.isCustom,
          }
        : {}),
      isOptimistic: true,
    };

    if (
      movingPiece.type === "king" &&
      move.from.row === move.to.row &&
      Math.abs(move.to.col - move.from.col) === 2
    ) {
      const direction = move.to.col > move.from.col ? 1 : -1;
      for (
        let rookCol = move.from.col + direction;
        rookCol >= 0 && rookCol < board[move.from.row].length;
        rookCol += direction
      ) {
        const candidate = board[move.from.row][rookCol];
        if (!candidate) continue;
        if (rookCol === move.to.col && candidate.pieceId === movingPiece.pieceId) {
          continue;
        }
        if (candidate.type === "rook" && candidate.color === movingPiece.color) {
          board[move.from.row][rookCol] = null;
          board[move.from.row][move.from.col + direction] = {
            ...candidate,
            isOptimistic: true,
          };
        }
        break;
      }
    }
  }

  return { ...game, board };
}
