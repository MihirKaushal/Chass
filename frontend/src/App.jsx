import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  completeGambitHandoff,
  completeSetupHandoff,
  createGame,
  getCatalog,
  getGame,
  getGameHistory,
  joinGame,
  makeMove,
  readyGambitDeployment,
  replaceInvite,
  requestRematch,
  selectAbility,
  updateGambitDeployment,
  updateGambitDraft,
  useGameAction,
  useCommandPower,
} from "./api/gameApi";
import OnlineLobby from "./components/OnlineLobby";
import SiteFooter from "./components/SiteFooter";
import TopNav from "./components/TopNav";
import {
  createInviteUrl,
  loadGameSession,
  mergeHistoryRecords,
  playerHasAbility,
  saveGameSession,
  updateGameSession,
} from "./gameSession";
import useGameSocket from "./hooks/useGameSocket";
import CustomizePage from "./pages/CustomizePage";
import GambitPage from "./pages/GambitPage";
import HomePage from "./pages/HomePage";
import JoinPage from "./pages/JoinPage";
import PlayPage from "./pages/PlayPage";
import AbilitySelectionPage, { AbilityHandoffPage } from "./pages/AbilitySelectionPage";
import { navigate, useRoute } from "./routing";


const FINISHED_STATUSES = new Set([
  "checkmate",
  "stalemate",
  "score_target",
  "king_capture",
  "points",
  "elimination",
  "time",
  "royal_score",
  "center_dominion",
  "royal_center",
  "check_race",
  "draw",
]);

function colorLabel(color) {
  return color ? color.charAt(0).toUpperCase() + color.slice(1) : "";
}

function oppositeColor(color) {
  if (color === "white") {
    return "black";
  }
  if (color === "black") {
    return "white";
  }
  return "";
}

function findRule(rules, ruleId) {
  return rules.find((rule) => rule.id === ruleId);
}

function buildEndgameMessage(game) {
  if (game.result?.description) {
    return game.result.description;
  }
  const winner = game.winner;
  const winnerLabel = colorLabel(winner);
  const loserLabel = colorLabel(oppositeColor(winner));

  if (game.gameStatus === "checkmate" && winner) {
    return `${winnerLabel} won! ${winnerLabel} checkmated ${loserLabel}'s King.`;
  }

  if (game.gameStatus === "score_target" && winner) {
    const scoreTargetRule = findRule(game.rules, "score_target_win");
    const targetScore = Number(scoreTargetRule?.params?.targetScore ?? 21);
    const normalizedTarget = Number.isFinite(targetScore) ? targetScore : 21;
    return `${winnerLabel} won! ${winnerLabel} got to ${normalizedTarget} point${normalizedTarget === 1 ? "" : "s"}.`;
  }

  if (game.gameStatus === "stalemate") {
    return "Stalemate! Neither side has a legal move.";
  }

  return winner ? `${winnerLabel} won!` : "Game over.";
}

function RestartRequestPanel({ game, playerColor, onRespond, actionLoading }) {
  if (game.rematch?.status !== "pending") {
    return null;
  }

  const approvals = game.rematch.approvals || {};
  const requestedBy = game.rematch.requestedBy;
  const onlineApproved = playerColor ? approvals[playerColor] : false;
  const localUnapproved = ["white", "black"].filter((color) => !approvals[color]);

  return (
    <section className="restart-request" aria-live="polite">
      <div>
        <span className="eyebrow">Restart Requested</span>
        <strong>{colorLabel(requestedBy)} wants to start this configuration again.</strong>
        <small>A new game starts only after both players approve.</small>
      </div>
      <div className="restart-approvals">
        {["white", "black"].map((color) => (
          <span key={color} className={approvals[color] ? "approved" : ""}>
            {colorLabel(color)}: {approvals[color] ? "Approved" : "Waiting"}
          </span>
        ))}
      </div>
      <div className="restart-actions">
        {game.mode === "online" && !onlineApproved ? (
          <>
            <button type="button" disabled={actionLoading} onClick={() => onRespond("accept")}>
              Approve Restart
            </button>
            <button type="button" className="secondary" disabled={actionLoading} onClick={() => onRespond("decline")}>
              Decline
            </button>
          </>
        ) : null}
        {game.mode === "online" && onlineApproved && requestedBy === playerColor ? (
          <button type="button" className="secondary" disabled={actionLoading} onClick={() => onRespond("cancel")}>
            Cancel Request
          </button>
        ) : null}
        {game.mode === "local" ? localUnapproved.map((color) => (
          <button type="button" key={color} disabled={actionLoading} onClick={() => onRespond("accept", color)}>
            {colorLabel(color)} Approves
          </button>
        )) : null}
        {game.mode === "local" && requestedBy ? (
          <button type="button" className="secondary" disabled={actionLoading} onClick={() => onRespond("cancel", requestedBy)}>
            Cancel Request
          </button>
        ) : null}
      </div>
    </section>
  );
}

function sessionFromResponse(response) {
  const inviteUrl = response.inviteToken
    ? createInviteUrl(response.inviteToken)
    : response.inviteUrl || null;

  return {
    gameId: response.game.id,
    mode: response.game.mode,
    variant: response.game.variant,
    token: response.playerToken,
    color: response.playerColor,
    role: response.role,
    inviteToken: response.inviteToken,
    inviteCode: response.inviteCode || response.inviteToken || null,
    inviteUrl,
    inviteExpiresAt: response.inviteExpiresAt,
  };
}

function GameWorkspace({ gameId }) {
  const [session, setSession] = useState(() => loadGameSession(gameId));
  const [game, setGame] = useState(null);
  const gameRef = useRef(null);
  const [catalog, setCatalog] = useState(null);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [pendingPromotion, setPendingPromotion] = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyArchive, setHistoryArchive] = useState({
    gameId: null,
    epoch: null,
    records: [],
    hasMore: false,
    nextBefore: null,
  });
  const [error, setError] = useState("");
  const [socketMessage, setSocketMessage] = useState("");
  const [presence, setPresence] = useState({ white: false, black: false });
  const [boardFlipped, setBoardFlipped] = useState(
    session?.mode === "online" && session?.color === "black"
  );
  const [autoBoardFlipEnabled, setAutoBoardFlipEnabled] = useState(
    session?.mode !== "online"
  );
  const [endgameMessage, setEndgameMessage] = useState("");
  const [showEndgameModal, setShowEndgameModal] = useState(false);
  const [showLocalRestartChooser, setShowLocalRestartChooser] = useState(false);
  const lastEndgameSignatureRef = useRef("");
  const moveTrackerRef = useRef({ gameId: "", moveCount: 0 });

  useEffect(() => {
    getCatalog().then(setCatalog).catch(() => {});
  }, []);

  const applyIncomingGame = useCallback(
    (incoming) => {
      if (!incoming || incoming.id !== gameId) {
        return;
      }

      const current = gameRef.current;
      if (current && incoming.version < current.version) {
        return;
      }

      gameRef.current = incoming;
      setGame(incoming);
      setInitialLoading(false);
    },
    [gameId]
  );

  const refreshGame = useCallback(async () => {
    const latest = await getGame(gameId, session?.token);
    applyIncomingGame(latest);

    if (!session && latest.mode === "local") {
      const localSession = {
        gameId,
        mode: "local",
        role: "local",
        token: null,
        color: null,
      };
      saveGameSession(gameId, localSession);
      setSession(localSession);
    }

    return latest;
  }, [applyIncomingGame, gameId, session]);

  useEffect(() => {
    let cancelled = false;
    setInitialLoading(true);
    setError("");

    getGame(gameId, session?.token)
      .then((latest) => {
        if (cancelled) {
          return;
        }
        applyIncomingGame(latest);
        if (!session && latest.mode === "local") {
          const localSession = {
            gameId,
            mode: "local",
            role: "local",
            token: null,
            color: null,
          };
          saveGameSession(gameId, localSession);
          setSession(localSession);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError.message);
          setInitialLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [applyIncomingGame, gameId, session?.token]);

  const connectionStatus = useGameSocket({
    gameId,
    token: session?.token,
    enabled: Boolean(game),
    onGame: applyIncomingGame,
    onPresence: (payload) => setPresence(payload.connected || { white: false, black: false }),
    onEvent: (payload) => {
      if (payload.type === "player_joined") {
        setSocketMessage(`${colorLabel(payload.color)} joined the game.`);
      }
    },
    onError: setSocketMessage,
  });

  const selectedMoves = useMemo(() => {
    if (!game || !selectedSquare) {
      return [];
    }
    return game.validMoves.filter(
      (move) =>
        move.from.row === selectedSquare.row && move.from.col === selectedSquare.col
    );
  }, [game, selectedSquare]);

  const canRequestRestart = Boolean(game?.ready && game?.phase !== "lobby");
  const canMove =
    Boolean(game?.ready) &&
    game?.phase === "play" &&
    (game?.mode === "local" || session?.color === game?.currentPlayer) &&
    !FINISHED_STATUSES.has(game?.gameStatus) &&
    !game?.winner;

  const historyGame = useMemo(() => {
    if (!game) return null;
    const epoch = game.historyPagination?.epoch ?? 0;
    const archiveMatches =
      historyArchive.gameId === game.id && historyArchive.epoch === epoch;
    return {
      ...game,
      history: mergeHistoryRecords(
        archiveMatches ? historyArchive.records : [],
        game.history || []
      ),
      historyPagination: {
        ...(game.historyPagination || {}),
        ...(archiveMatches
          ? {
              hasMore: historyArchive.hasMore,
              nextBefore: historyArchive.nextBefore,
            }
          : {}),
      },
    };
  }, [game, historyArchive]);

  const handleLoadEarlierHistory = useCallback(async () => {
    if (!game || historyLoading) return;
    const epoch = game.historyPagination?.epoch ?? 0;
    const archiveMatches =
      historyArchive.gameId === game.id && historyArchive.epoch === epoch;
    const pagination = archiveMatches ? historyArchive : game.historyPagination;
    if (!pagination?.hasMore || !pagination.nextBefore) return;

    setHistoryLoading(true);
    setError("");
    try {
      const page = await getGameHistory(
        game.id,
        { before: pagination.nextBefore, limit: 50 },
        session?.token
      );
      if (page.pagination.epoch !== epoch) return;
      setHistoryArchive((current) => {
        const currentMatches = current.gameId === game.id && current.epoch === epoch;
        return {
          gameId: game.id,
          epoch,
          records: mergeHistoryRecords(
            currentMatches ? current.records : [],
            page.history
          ),
          hasMore: page.pagination.hasMore,
          nextBefore: page.pagination.nextBefore,
        };
      });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setHistoryLoading(false);
    }
  }, [game, historyArchive, historyLoading, session?.token]);

  useEffect(() => {
    setSelectedSquare(null);
    setPendingPromotion(null);
  }, [game?.version]);

  useEffect(() => {
    if (game?.mode !== "online" || !session?.color) {
      return;
    }

    setAutoBoardFlipEnabled(false);
    setBoardFlipped(session.color === "black");
  }, [game?.id, game?.mode, session?.color]);

  useEffect(() => {
    if (game?.variant !== "gambit" || game.phase !== "deployment") {
      return;
    }
    const setupColor = game.gambit?.editableColor || game.gambit?.viewerColor;
    if (setupColor) {
      setBoardFlipped(setupColor === "black");
    }
  }, [game?.gambit?.editableColor, game?.gambit?.viewerColor, game?.phase, game?.variant]);

  useEffect(() => {
    if (
      game?.variant === "gambit" &&
      game.phase === "play" &&
      (game.historyPagination?.totalMoves ?? game.history.length) === 0
    ) {
      setBoardFlipped(game.mode === "online" ? session?.color === "black" : false);
      setAutoBoardFlipEnabled(game.mode !== "online");
    }
  }, [game?.history?.length, game?.mode, game?.phase, game?.variant, session?.color]);

  useEffect(() => {
    if (!socketMessage) {
      return undefined;
    }
    const timer = window.setTimeout(() => setSocketMessage(""), 4500);
    return () => window.clearTimeout(timer);
  }, [socketMessage]);

  useEffect(() => {
    if (
      !game?.clock ||
      game.phase !== "play" ||
      FINISHED_STATUSES.has(game.gameStatus)
    ) {
      return undefined;
    }

    const activeColor = game.clock.activeColor;
    const storedRemaining = Number(game.clock.remainingSeconds?.[activeColor] ?? 0);
    const startedAt = new Date(game.clock.turnStartedAt).getTime();
    const elapsedSeconds = Number.isFinite(startedAt)
      ? Math.max(0, (Date.now() - startedAt) / 1000)
      : 0;
    const refreshDelay = Math.max(100, (storedRemaining - elapsedSeconds) * 1000 + 150);
    const timer = window.setTimeout(() => {
      refreshGame().catch((requestError) => setError(requestError.message));
    }, refreshDelay);
    return () => window.clearTimeout(timer);
  }, [
    game?.clock?.activeColor,
    game?.clock?.remainingSeconds,
    game?.clock?.turnStartedAt,
    game?.gameStatus,
    game?.phase,
    refreshGame,
  ]);

  useEffect(() => {
    if (!game) {
      return;
    }

    const gameEnded = FINISHED_STATUSES.has(game.gameStatus) || Boolean(game.winner);
    if (!gameEnded) {
      setShowEndgameModal(false);
      setEndgameMessage("");
      lastEndgameSignatureRef.current = "";
      return;
    }

    const signature = [
      game.id,
      game.gameStatus,
      game.winner ?? "none",
      game.historyPagination?.totalMoves ?? game.history.length,
    ].join(":");
    if (lastEndgameSignatureRef.current === signature) {
      return;
    }

    lastEndgameSignatureRef.current = signature;
    setEndgameMessage(buildEndgameMessage(game));
    setShowEndgameModal(true);
  }, [game]);

  useEffect(() => {
    if (!game?.id) {
      return;
    }

    const moveCount = game.historyPagination?.totalMoves ?? game.history?.length ?? 0;
    const tracker = moveTrackerRef.current;
    if (tracker.gameId !== game.id) {
      moveTrackerRef.current = { gameId: game.id, moveCount };
      return;
    }

    const diff = moveCount - tracker.moveCount;
    if (autoBoardFlipEnabled && diff > 0 && diff % 2 === 1) {
      setBoardFlipped(game.currentPlayer === "black");
    }
    moveTrackerRef.current = { gameId: game.id, moveCount };
  }, [
    autoBoardFlipEnabled,
    game?.id,
    game?.history?.length,
    game?.historyPagination?.totalMoves,
  ]);

  const runAction = async (operation) => {
    setActionLoading(true);
    setError("");
    try {
      return await operation();
    } catch (requestError) {
      setError(requestError.message);
      if (requestError instanceof ApiError && requestError.status === 409) {
        await refreshGame().catch(() => {});
      }
      throw requestError;
    } finally {
      setActionLoading(false);
    }
  };

  const mutate = async (apiFunction, payload) => {
    const current = gameRef.current;
    if (!current) {
      throw new Error("Game state is not loaded yet.");
    }

    const updated = await apiFunction(
      gameId,
      { ...payload, expectedVersion: current.version },
      session?.token
    );
    applyIncomingGame(updated);
    return updated;
  };

  const submitMove = async (fromSquare, toSquare, promotion = null) => {
    try {
      await runAction(() =>
        mutate(makeMove, {
          fromRow: fromSquare.row,
          fromCol: fromSquare.col,
          toRow: toSquare.row,
          toCol: toSquare.col,
          ...(promotion ? { promotion } : {}),
        })
      );
    } catch {
      // The shared error banner explains rejected moves.
    }
  };

  const handleDeploymentChange = async (payload) => {
    try {
      await runAction(() => mutate(updateGambitDeployment, payload));
    } catch {
      // The shared error banner explains rejected deployment changes.
    }
  };

  const handleGambitDraft = async (payload) => {
    try {
      await runAction(() => mutate(updateGambitDraft, payload));
    } catch {
      // The shared error banner explains rejected draft actions.
    }
  };

  const handleGambitReady = async () => {
    try {
      await runAction(() => mutate(readyGambitDeployment, {}));
    } catch {
      // The shared error banner explains why the army cannot lock in yet.
    }
  };

  const handleGambitHandoff = async () => {
    try {
      await runAction(() => mutate(completeGambitHandoff, {}));
    } catch {
      // The shared error banner explains handoff failures.
    }
  };

  const handleCommandPower = async (payload) => {
    try {
      await runAction(() => mutate(useCommandPower, payload));
    } catch {
      // The shared error banner explains rejected command actions.
    }
  };

  const handleSpecialAction = async (action) => {
    try {
      await runAction(() =>
        mutate(useGameAction, {
          actionType: action.actionType,
          source: action.source,
          target: action.target,
          secondary: action.secondary,
          params: action.params || {},
        })
      );
    } catch {
      // The shared error banner explains rejected special actions.
    }
  };

  const handleAbilitySelection = async (abilityIds) => {
    try {
      await runAction(() => mutate(selectAbility, { abilityIds }));
    } catch {
      // The shared error banner explains rejected ability selections.
    }
  };

  const handleSetupHandoff = async () => {
    try {
      await runAction(() => mutate(completeSetupHandoff, {}));
    } catch {
      // The shared error banner explains handoff failures.
    }
  };

  const handleSquareClick = (row, col) => {
    if (!game || actionLoading || !canMove) {
      return;
    }

    const clickedPiece = game.board[row][col];
    if (!selectedSquare) {
      if (clickedPiece && clickedPiece.color === game.currentPlayer) {
        setSelectedSquare({ row, col });
      }
      return;
    }

    if (selectedSquare.row === row && selectedSquare.col === col) {
      setSelectedSquare(null);
      return;
    }

    const chosenMove = selectedMoves.find(
      (move) => move.to.row === row && move.to.col === col
    );
    if (chosenMove) {
      const movingPiece = game.board[selectedSquare.row][selectedSquare.col];
      const finalRank =
        movingPiece?.color === "white" ? 0 : (game.boardRows ?? game.boardSize) - 1;
      if (movingPiece?.type === "pawn" && row === finalRank) {
        setPendingPromotion({ from: selectedSquare, to: { row, col } });
      } else {
        submitMove(selectedSquare, { row, col });
      }
      return;
    }

    if (clickedPiece && clickedPiece.color === game.currentPlayer) {
      setSelectedSquare({ row, col });
    } else {
      setSelectedSquare(null);
    }
  };

  const handleRematch = async (action, color = null) => {
    try {
      await runAction(() =>
        mutate(requestRematch, {
          action,
          ...(color ? { color } : {}),
        })
      );
      setShowLocalRestartChooser(false);
      setShowEndgameModal(false);
      if (game.mode === "online") {
        setBoardFlipped(session?.color === "black");
      } else if (action === "accept") {
        setBoardFlipped(false);
      }
    } catch {
      // The shared error banner explains restart failures.
    }
  };

  const handleRestartRequest = () => {
    setShowEndgameModal(false);
    if (game.mode === "local") {
      setShowLocalRestartChooser(true);
      return;
    }
    handleRematch("request");
  };

  const customizeCurrentGame = () => {
    const configuration = {
      ...game.configuration,
      piecePoints: Object.fromEntries(
        (game.pieceDefinitions || []).map((piece) => [piece.type, piece.points])
      ),
    };
    window.sessionStorage.setItem(
      "chass-customize-draft",
      JSON.stringify({
        boardRows: game.boardRows ?? game.boardSize,
        boardCols: game.boardCols ?? game.boardSize,
        configuration,
      })
    );
    navigate("/customize?source=current");
  };

  const handleReplaceInvite = async () => {
    try {
      const invite = await runAction(() => replaceInvite(gameId, session?.token));
      const updatedSession = updateGameSession(gameId, {
        inviteToken: invite.inviteToken,
        inviteCode: invite.inviteCode || invite.inviteToken,
        inviteUrl: createInviteUrl(invite.inviteToken),
        inviteExpiresAt: invite.inviteExpiresAt,
      });
      setSession(updatedSession);
    } catch {
      // The shared error banner explains invite failures.
    }
  };

  if (initialLoading && !game) {
    return (
      <div className="app-shell centered">
        <div className="loading-card">
          <span className="loading-mark" />
          <h1>Loading the board</h1>
          <p>Free hosts may need a moment to wake up.</p>
        </div>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="app-shell centered">
        <div className="loading-card">
          <h1>Game unavailable</h1>
          <p>{error || "This game could not be loaded."}</p>
          <div className="button-row">
            <button type="button" onClick={() => window.location.reload()}>
              Try Again
            </button>
            <button type="button" className="secondary" onClick={() => navigate("/")}>
              Back Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell page-frame">
      <TopNav
        onReset={handleRestartRequest}
        onHome={() => navigate("/")}
        onCustomize={() => navigate("/customize")}
        currentPlayer={game.currentPlayer}
        gameStatus={game.gameStatus}
        winner={game.winner}
        onFlipBoard={() => setBoardFlipped((current) => !current)}
        onToggleAutoBoardFlip={() => setAutoBoardFlipEnabled((current) => !current)}
        boardFlipped={boardFlipped}
        autoBoardFlipEnabled={autoBoardFlipEnabled}
        canReset={canRequestRestart}
        mode={game.mode}
        playerColor={session?.color}
        connectionStatus={connectionStatus}
        variant={game.variant}
        phase={game.phase}
      />

      {game.mode === "online" ? (
        <OnlineLobby
          game={game}
          session={session}
          presence={presence}
          connectionStatus={connectionStatus}
          onReplaceInvite={handleReplaceInvite}
        />
      ) : null}

      {error ? <p className="global-error">{error}</p> : null}
      {socketMessage ? <p className="sync-message">{socketMessage}</p> : null}
      {actionLoading ? <p className="global-loading">Syncing authoritative game state...</p> : null}
      <RestartRequestPanel
        game={game}
        playerColor={session?.color}
        onRespond={handleRematch}
        actionLoading={actionLoading}
      />
      {!canMove &&
      game.ready &&
      game.mode === "online" &&
      game.phase === "play" &&
      !game.winner ? (
        <p className="turn-notice">
          You are {colorLabel(session?.color)}. Waiting for {colorLabel(game.currentPlayer)} to
          move.
        </p>
      ) : null}

      {game.phase === "ability_selection" ? (
        <AbilitySelectionPage
          game={game}
          catalog={catalog}
          onSelect={handleAbilitySelection}
          actionLoading={actionLoading}
        />
      ) : game.phase === "handoff" &&
        game.configuration?.specialAbilities?.enabled &&
        !game.abilities?.selected?.black?.length ? (
        <AbilityHandoffPage
          game={game}
          onContinue={handleSetupHandoff}
          actionLoading={actionLoading}
        />
      ) : game.variant === "gambit" ? (
        <GambitPage
          game={historyGame}
          selectedSquare={selectedSquare}
          onSquareClick={handleSquareClick}
          boardFlipped={boardFlipped}
          interactive={canMove && !actionLoading}
          actionLoading={actionLoading}
          onDeploymentChange={handleDeploymentChange}
          onDraft={handleGambitDraft}
          onReady={handleGambitReady}
          onHandoff={handleGambitHandoff}
          onPower={handleCommandPower}
          onAction={handleSpecialAction}
          catalog={catalog}
          onLoadEarlierHistory={handleLoadEarlierHistory}
          historyLoading={historyLoading}
        />
      ) : (
        <PlayPage
          game={historyGame}
          selectedSquare={selectedSquare}
          onSquareClick={handleSquareClick}
          boardFlipped={boardFlipped}
          interactive={canMove && !actionLoading}
          onAction={handleSpecialAction}
          actionLoading={actionLoading}
          onPower={handleCommandPower}
          catalog={catalog}
          onLoadEarlierHistory={handleLoadEarlierHistory}
          historyLoading={historyLoading}
        />
      )}

      <SiteFooter />

      {pendingPromotion ? (
        <div className="endgame-modal-backdrop" role="presentation">
          <div className="promotion-modal" role="dialog" aria-modal="true">
            <span className="eyebrow">Final Rank Reached</span>
            <h2>Choose A Pawn Action</h2>
            <p>Promote normally, or use Kamikaze if that is your selected ability.</p>
            <div className="promotion-options">
              {["queen", "rook", "bishop", "knight"].map((pieceType) => (
                <button
                  type="button"
                  key={pieceType}
                  onClick={() => {
                    const pending = pendingPromotion;
                    setPendingPromotion(null);
                    submitMove(pending.from, pending.to, pieceType);
                  }}
                >
                  {colorLabel(pieceType)}
                </button>
              ))}
              {playerHasAbility(game, game.currentPlayer, "kamikaze") ? (
                <button
                  type="button"
                  className="kamikaze-choice"
                  onClick={() => {
                    const pending = pendingPromotion;
                    setPendingPromotion(null);
                    submitMove(pending.from, pending.to, "kamikaze");
                  }}
                >
                  ✹ Kamikaze
                </button>
              ) : null}
            </div>
            <button type="button" className="text-button" onClick={() => setPendingPromotion(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {showLocalRestartChooser ? (
        <div className="endgame-modal-backdrop" role="presentation">
          <div className="endgame-modal" role="dialog" aria-modal="true" aria-labelledby="restart-seat-title">
            <span className="eyebrow">Same-Device Approval</span>
            <h2 id="restart-seat-title">Who Is Requesting?</h2>
            <p>The other player must approve before the board resets.</p>
            <div className="button-row">
              {["white", "black"].map((color) => (
                <button type="button" key={color} disabled={actionLoading} onClick={() => handleRematch("request", color)}>
                  {colorLabel(color)} Requests Restart
                </button>
              ))}
              <button type="button" className="secondary" onClick={() => setShowLocalRestartChooser(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showEndgameModal ? (
        <div className="endgame-modal-backdrop" role="presentation">
          <div className="endgame-modal" role="dialog" aria-modal="true" aria-live="polite">
            <span className="eyebrow">Final position</span>
            <h2>Match Finished</h2>
            <p>{endgameMessage}</p>
            <div className="button-row">
              {canRequestRestart ? (
                <button type="button" onClick={handleRestartRequest}>
                  Play Again
                </button>
              ) : null}
              <button type="button" className="secondary" onClick={customizeCurrentGame}>
                Customize This Game
              </button>
              <button type="button" className="secondary" onClick={() => navigate("/")}>
                Home
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setShowEndgameModal(false)}
              >
                Review Board
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function App() {
  const route = useRoute();

  const handleCreate = async (request) => {
    const payload =
      typeof request === "string"
        ? {
            mode: request,
            variant: "classic",
            boardRows: 8,
            boardCols: 8,
            rules: [],
            customPieces: [],
          }
        : request;
    const response = await createGame(payload);
    const session = sessionFromResponse(response);
    saveGameSession(response.game.id, session);
    navigate(`/game/${response.game.id}`);
  };

  const handleJoin = async (inviteToken) => {
    const response = await joinGame(inviteToken);
    const session = sessionFromResponse(response);
    saveGameSession(response.game.id, session);
    navigate(`/game/${response.game.id}`, { replace: true });
  };

  if (route.name === "join") {
    return (
      <JoinPage
        inviteToken={route.inviteToken}
        onJoin={handleJoin}
        onHome={() => navigate("/")}
      />
    );
  }

  if (route.name === "game") {
    return <GameWorkspace key={route.gameId} gameId={route.gameId} />;
  }

  if (route.name === "customize") {
    return (
      <CustomizePage
        onCreate={handleCreate}
        onPlay={() => navigate("/")}
        initialPreset={route.preset}
      />
    );
  }

  return (
    <HomePage
      onCreate={handleCreate}
      onCustomize={() => navigate("/customize")}
      onJoinCode={(inviteCode) => navigate(`/join/${encodeURIComponent(inviteCode)}`)}
    />
  );
}

export default App;
