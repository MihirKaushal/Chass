export const SOUND_PREFERENCE_STORAGE_KEY = "chass:sound-preferences";
export const DEFAULT_SOUND_VOLUME = 0.7;

export const SOUND_ASSETS = {
  armyLockedIn: "/sounds/chass_army_locked_in.mp3",
  capture: "/sounds/chass_capture.mp3",
  check: "/sounds/chass_check.mp3",
  clock: "/sounds/chass_clock_ticking.mp3",
  draw: "/sounds/chass_draw_stalemate.mp3",
  error: "/sounds/chass_error.mp3",
  explosion: "/sounds/chass_explosion.mp3",
  gameStart: "/sounds/chass_game_start.mp3",
  heavyMovement: "/sounds/chass_heavy_movement.mp3",
  move: "/sounds/chass_piece_move.mp3",
  transformation: "/sounds/chass_piece_transformation.mp3",
  scorch: "/sounds/chass_scorch.mp3",
  win: "/sounds/chass_win.mp3",
  lose: "/sounds/chass_lose.mp3",
};

export const CLOCK_SOUND_THRESHOLDS = [
  { seconds: 60, durationMs: 5000, loop: false },
  { seconds: 30, durationMs: 5000, loop: false },
  { seconds: 10, durationMs: 10000, loop: true },
];

const MOVEMENT_ACTION_TYPES = new Set([
  "move",
  "move_barricade",
  "episcopal",
  "getaway",
]);

const EXPLOSION_ACTION_TYPES = new Set([
  "catapult_projectile",
  "demolish_barricade",
]);

const TRANSFORMATION_ACTION_TYPES = new Set([
  "necromancy",
  "reinforce",
  "evolve",
  "stronghold",
]);

const DRAW_STATUSES = new Set(["draw", "stalemate"]);
const ACTIVE_GAME_STATUSES = new Set(["active", "check"]);

export function clampSoundVolume(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return DEFAULT_SOUND_VOLUME;
  return Math.max(0, Math.min(1, numericValue));
}

export function normalizeSoundPreferences(preferences = {}) {
  const volume = clampSoundVolume(preferences.volume ?? DEFAULT_SOUND_VOLUME);
  return {
    volume,
    muted: volume === 0 || Boolean(preferences.muted),
  };
}

export function readSoundPreferences(storage) {
  try {
    const serialized = storage?.getItem(SOUND_PREFERENCE_STORAGE_KEY);
    return normalizeSoundPreferences(serialized ? JSON.parse(serialized) : {});
  } catch {
    return normalizeSoundPreferences();
  }
}

export function writeSoundPreferences(storage, preferences) {
  const normalized = normalizeSoundPreferences(preferences);
  try {
    storage?.setItem(SOUND_PREFERENCE_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Sound controls still work for this page when browser storage is unavailable.
  }
  return normalized;
}

export function isMovementActionType(actionType) {
  return MOVEMENT_ACTION_TYPES.has(actionType || "move");
}

function movementSignature(actionType, player, from, to) {
  if (!isMovementActionType(actionType) || !from || !to) return null;
  return [
    actionType || "move",
    player || "unknown",
    from.row,
    from.col,
    to.row,
    to.col,
  ].join(":");
}

function uniqueSounds(sounds) {
  return [...new Set(sounds.filter((sound) => SOUND_ASSETS[sound]))];
}

function pieceStates(board) {
  const states = {};
  (board || []).forEach((row) => {
    (row || []).forEach((piece) => {
      if (!piece?.pieceId) return;
      states[piece.pieceId] = {
        type: piece.type,
        color: piece.color,
        cannibalForm: piece.runtime?.cannibal_form || null,
        loveUntilTurn: piece.runtime?.love_until_turn ?? null,
      };
    });
  });
  return states;
}

function transformationOccurred(previous, current) {
  if (!previous?.pieceStates || !current?.pieceStates) return false;
  return Object.entries(current.pieceStates).some(([pieceId, currentPiece]) => {
    const previousPiece = previous.pieceStates[pieceId];
    return previousPiece && (
      previousPiece.type !== currentPiece.type
      || previousPiece.color !== currentPiece.color
      || previousPiece.cannibalForm !== currentPiece.cannibalForm
      || previousPiece.loveUntilTurn !== currentPiece.loveUntilTurn
    );
  });
}

function isKamikazeRecord(record, current) {
  if (!record || record.actionType !== "move" || record.piece !== "pawn") return false;
  if (record.captures.some((capture) => capture.reason?.startsWith("Kamikaze"))) {
    return true;
  }
  return current.lastTargetPiece == null;
}

function recordSoundCues(previous, current) {
  const record = current.lastRecord;
  if (!record || current.moveCount <= previous.moveCount) return [];

  const cues = [];
  const hasCaptures = record.captures.length > 0;
  const exploded = EXPLOSION_ACTION_TYPES.has(record.actionType)
    || isKamikazeRecord(record, current);
  const heavyMovement = record.actionType === "move_barricade"
    || record.piece === "elephant";

  if (record.actionType === "scorch") {
    cues.push("scorch");
  } else if (exploded) {
    cues.push("explosion");
    if (record.actionType === "catapult_projectile" && hasCaptures) {
      cues.push("capture");
    }
  } else if (heavyMovement) {
    cues.push("heavyMovement");
    if (hasCaptures) cues.push("capture");
  } else if (TRANSFORMATION_ACTION_TYPES.has(record.actionType)) {
    cues.push("transformation");
  } else if (hasCaptures) {
    cues.push("capture");
  } else if (isMovementActionType(record.actionType)) {
    cues.push("move");
  }

  if (transformationOccurred(previous, current)) {
    cues.push("transformation");
  }
  return uniqueSounds(cues);
}

export function gameSoundSnapshot(game, playerColor = null) {
  if (!game?.id) return null;
  const history = Array.isArray(game.history) ? game.history : [];
  const lastRecord = history[history.length - 1] || null;
  const lastActionType = lastRecord?.actionType || (history.length ? "move" : null);
  const targetPiece = lastRecord?.to
    ? game.board?.[lastRecord.to.row]?.[lastRecord.to.col] || null
    : null;

  return {
    gameId: game.id,
    mode: game.mode,
    playerColor,
    currentPlayer: game.currentPlayer || null,
    version: Number(game.version) || 0,
    phase: game.phase || null,
    gameStatus: game.gameStatus || null,
    winner: game.winner || null,
    resultReasonCode: game.result?.reasonCode || null,
    historyEpoch: Number(game.historyPagination?.epoch) || 0,
    moveCount: Number(game.historyPagination?.totalMoves ?? history.length) || 0,
    lastActionType,
    lastRecord: lastRecord
      ? {
          actionType: lastActionType,
          player: lastRecord.player || null,
          piece: lastRecord.piece || null,
          from: lastRecord.from || null,
          to: lastRecord.to || null,
          captures: Array.isArray(lastRecord.captures) ? lastRecord.captures : [],
        }
      : null,
    lastTargetPiece: targetPiece
      ? { pieceId: targetPiece.pieceId, type: targetPiece.type, color: targetPiece.color }
      : null,
    lastMovementSignature: movementSignature(
      lastActionType,
      lastRecord?.player,
      lastRecord?.from,
      lastRecord?.to
    ),
    pieceStates: pieceStates(game.board),
    deploymentReady: {
      white: Boolean(game.gambit?.deploymentReady?.white),
      black: Boolean(game.gambit?.deploymentReady?.black),
    },
    checkCount: Number(game.checkRace?.checks?.white || 0)
      + Number(game.checkRace?.checks?.black || 0),
  };
}

export function optimisticMoveSoundCues(pendingMove) {
  if (!pendingMove?.move) return [];
  const captures = Array.isArray(pendingMove.move.captures)
    ? pendingMove.move.captures
    : [];
  const cues = [];

  if (pendingMove.promotion === "kamikaze") {
    cues.push("explosion");
  } else if (pendingMove.pieceType === "elephant") {
    cues.push("heavyMovement");
    if (captures.length) cues.push("capture");
  } else {
    cues.push(captures.length ? "capture" : "move");
  }

  if (
    (pendingMove.promotion && pendingMove.promotion !== "kamikaze")
    || (pendingMove.pieceType === "cannibal" && captures.length)
  ) {
    cues.push("transformation");
  }
  return uniqueSounds(cues);
}

export function optimisticMoveSoundToken(snapshot, pendingMove) {
  if (!snapshot || pendingMove?.id == null || !pendingMove.move) return null;
  if (
    pendingMove.baseVersion != null
    && snapshot.version !== Number(pendingMove.baseVersion)
  ) {
    return null;
  }

  const signature = movementSignature(
    "move",
    snapshot.currentPlayer,
    pendingMove.move.from,
    pendingMove.move.to
  );
  if (!signature) return null;

  return {
    gameId: snapshot.gameId,
    pendingId: pendingMove.id,
    baseMoveCount: snapshot.moveCount,
    signature,
    cues: optimisticMoveSoundCues(pendingMove),
  };
}

export function confirmsOptimisticMove(token, previous, current) {
  return Boolean(
    token
    && previous
    && current
    && token.gameId === current.gameId
    && previous.gameId === current.gameId
    && current.moveCount > token.baseMoveCount
    && current.moveCount > previous.moveCount
    && current.lastMovementSignature === token.signature
  );
}

export function outcomeSoundForSnapshot(snapshot) {
  if (!snapshot?.winner) return null;
  if (snapshot.mode === "local") return "win";
  if (!["white", "black"].includes(snapshot.playerColor)) return null;
  return snapshot.winner === snapshot.playerColor ? "win" : "lose";
}

export function soundsForGameTransition(
  previous,
  current,
  { announceInitialStart = false } = {}
) {
  if (!current) return [];
  if (!previous) {
    return announceInitialStart && current.phase === "play" && current.moveCount === 0
      ? ["gameStart"]
      : [];
  }
  if (previous.gameId !== current.gameId) return [];

  const sounds = recordSoundCues(previous, current);
  const historyAdvanced = current.moveCount > previous.moveCount;
  const checkDelivered = (
    historyAdvanced
    && ["check", "checkmate"].includes(current.gameStatus)
    && current.resultReasonCode !== "kamikaze"
  ) || current.checkCount > previous.checkCount;
  if (checkDelivered) sounds.push("check");

  const newlyLockedArmies = ["white", "black"].filter(
    (color) => (
      current.deploymentReady?.[color]
      && !previous.deploymentReady?.[color]
    )
  ).length;
  if (newlyLockedArmies) sounds.push("armyLockedIn");

  if (current.phase === "play" && previous.phase !== "play") {
    sounds.push("gameStart");
  }

  if (current.winner && current.winner !== previous.winner) {
    const outcomeSound = outcomeSoundForSnapshot(current);
    if (outcomeSound) sounds.push(outcomeSound);
  } else if (
    DRAW_STATUSES.has(current.gameStatus)
    && current.gameStatus !== previous.gameStatus
  ) {
    sounds.push("draw");
  }

  return uniqueSounds(sounds);
}

export function soundForGameTransition(previous, current) {
  return soundsForGameTransition(previous, current).at(-1) || null;
}

export function clockSoundPlan(game, nowMs = Date.now()) {
  if (
    !game?.id
    || !game.clock
    || game.phase !== "play"
    || game.winner
    || !ACTIVE_GAME_STATUSES.has(game.gameStatus)
  ) {
    return null;
  }

  const activeColor = game.clock.activeColor;
  const initialSeconds = Number(game.clock.initialSeconds);
  const storedRemaining = Number(game.clock.remainingSeconds?.[activeColor]);
  const turnStartedAt = new Date(game.clock.turnStartedAt).getTime();
  if (
    !["white", "black"].includes(activeColor)
    || !Number.isFinite(initialSeconds)
    || !Number.isFinite(storedRemaining)
    || !Number.isFinite(turnStartedAt)
  ) {
    return null;
  }

  const elapsedSeconds = Math.max(0, (nowMs - turnStartedAt) / 1000);
  const remainingSeconds = Math.max(0, storedRemaining - elapsedSeconds);
  const epoch = Number(game.historyPagination?.epoch) || 0;
  return {
    gameId: game.id,
    epoch,
    activeColor,
    initialSeconds,
    remainingSeconds,
    events: CLOCK_SOUND_THRESHOLDS
      .filter(({ seconds }) => initialSeconds > seconds)
      .map((event) => ({
        ...event,
        key: `${game.id}:${epoch}:${activeColor}:${event.seconds}`,
        crossed: remainingSeconds <= event.seconds,
        delayMs: Math.max(0, (remainingSeconds - event.seconds) * 1000),
        activeDurationMs: event.loop
          ? Math.max(0, Math.min(event.durationMs, remainingSeconds * 1000))
          : event.durationMs,
        endAtMs: event.loop
          ? nowMs + Math.max(0, (remainingSeconds - event.seconds) * 1000)
            + Math.max(0, Math.min(event.durationMs, remainingSeconds * 1000))
          : null,
      })),
  };
}
