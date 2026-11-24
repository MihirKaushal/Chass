import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  completeGambitHandoff,
  completeSetupHandoff,
  createGame,
  importScannedGame,
  getCatalog,
  getGame,
  getGameHistory,
  getMatchAnalysis,
  joinGame,
  makeMove,
  readyGambitDeployment,
  replaceInvite,
  requestRematch,
  resignGame,
  respondToDraw,
  selectAbility,
  updateGambitDeployment,
  updateGambitDraft,
  useGameAction,
  useCommandPower,
} from "./api/gameApi";
import { botTurnIsPending, sessionForPublicGame } from "./botGame";
import OnlineLobby from "./components/OnlineLobby";
import PageSkeleton from "./components/PageSkeleton";
import SiteFooter from "./components/SiteFooter";
import TopNav from "./components/TopNav";
import Button from "./components/ui/Button";
import Dialog from "./components/ui/Dialog";
import StableStatus from "./components/ui/StableStatus";
import {
  createInviteUrl,
  loadGameSession,
  mergeHistoryRecords,
  playerHasAbility,
  projectPendingMove,
  saveGameSession,
  updateGameSession,
} from "./gameSession";
import { clockDeadlineDelayMs } from "./gameClock";
import { onlineInviteState } from "./onlineInviteState";
import useDocumentTitle from "./hooks/useDocumentTitle";
import useGameSocket from "./hooks/useGameSocket";
import useGameSounds from "./hooks/useGameSounds";
import { shouldConfirmGameNavigation } from "./leaveGameGuard";
import { fallbackPollDelayMs } from "./socketPolicy";
import { analysisMatchesGame } from "./matchPredictor";
import { gameDocumentTitle } from "./documentTitle";
import { browserLocalStorage, forgetRecentGame, recordRecentGame } from "./recentGames";
import GambitPage from "./pages/GambitPage";
import HomePage from "./pages/HomePage";
import JoinPage from "./pages/JoinPage";
import PlayPage from "./pages/PlayPage";
import AbilitySelectionPage, { AbilityHandoffPage } from "./pages/AbilitySelectionPage";
import { navigate, useNavigationBlocker, useRoute } from "./routing";
import { customizeSession } from "./customizeSession";
import { importWithReload } from "./lazyRoute";
import { navigationDestination } from "./siteNavigation";


// Larger, less common routes (and the bundled rulebook catalog they share) load on demand.
const CustomizePage = lazy(() => importWithReload(() => import("./pages/CustomizePage")));
const RulebookPage = lazy(() => importWithReload(() => import("./pages/RulebookPage")));
const ScannerPage = lazy(() => importWithReload(() => import("./pages/ScannerPage")));

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
  "resigned",
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
        <span className="eyebrow">Restart requested</span>
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
            <Button disabled={actionLoading} onClick={() => onRespond("accept")}>
              Approve restart
            </Button>
            <Button variant="secondary" disabled={actionLoading} onClick={() => onRespond("decline")}>
              Decline
            </Button>
          </>
        ) : null}
        {game.mode === "online" && onlineApproved && requestedBy === playerColor ? (
          <Button variant="secondary" disabled={actionLoading} onClick={() => onRespond("cancel")}>
            Cancel request
          </Button>
        ) : null}
        {game.mode === "local" ? localUnapproved.map((color) => (
          <Button key={color} disabled={actionLoading} onClick={() => onRespond("accept", color)}>
            {colorLabel(color)} approves
          </Button>
        )) : null}
        {game.mode === "local" && requestedBy ? (
          <Button variant="secondary" disabled={actionLoading} onClick={() => onRespond("cancel", requestedBy)}>
            Cancel request
          </Button>
        ) : null}
      </div>
    </section>
  );
}

function DrawOfferPanel({ game, playerColor, onRespond, actionLoading }) {
  const offeredBy = game.drawOfferedBy;
  if (!offeredBy) return null;

  const responder = oppositeColor(offeredBy);
  const online = game.mode === "online";
  const canAnswer = !online || playerColor === responder;
  const canWithdraw = !online || playerColor === offeredBy;

  return (
    <section className="restart-request draw-offer" aria-live="polite">
      <div>
        <span className="eyebrow">Draw offered</span>
        <strong>{colorLabel(offeredBy)} offers a draw.</strong>
        <small>
          {canAnswer
            ? `${colorLabel(responder)} can accept, decline, or decline by moving.`
            : "Waiting for your opponent to answer."}
        </small>
      </div>
      <div className="restart-actions">
        {canAnswer ? (
          <>
            <Button disabled={actionLoading} onClick={() => onRespond("accept", responder)}>
              {online ? "Accept draw" : `${colorLabel(responder)} accepts`}
            </Button>
            <Button variant="secondary" disabled={actionLoading} onClick={() => onRespond("decline", responder)}>
              {online ? "Decline" : `${colorLabel(responder)} declines`}
            </Button>
          </>
        ) : null}
        {canWithdraw ? (
          <Button variant="secondary" disabled={actionLoading} onClick={() => onRespond("cancel", offeredBy)}>
            Withdraw offer
          </Button>
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

function GameWorkspace({ gameId, initialGame = null, onBootstrapConsumed }) {
  const startedWithBootstrapRef = useRef(initialGame?.id === gameId);
  const [session, setSession] = useState(() => loadGameSession(gameId));
  const [game, setGame] = useState(initialGame);
  const gameRef = useRef(initialGame);
  const [catalog, setCatalog] = useState(null);
  const [catalogError, setCatalogError] = useState("");
  const [catalogRetryKey, setCatalogRetryKey] = useState(0);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [pendingPromotion, setPendingPromotion] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const pendingMoveIdRef = useRef(0);
  const [initialLoading, setInitialLoading] = useState(!initialGame);
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
  const [matchAnalysis, setMatchAnalysis] = useState(null);
  const [analysisRefreshing, setAnalysisRefreshing] = useState(false);
  const [analysisRetryKey, setAnalysisRetryKey] = useState(0);
  const [matchAnalysisEnabled, setMatchAnalysisEnabled] = useState(true);
  const [presence, setPresence] = useState({ white: false, black: false });
  const [boardFlipped, setBoardFlipped] = useState(
    ["online", "bot"].includes(session?.mode) && session?.color === "black"
  );
  const [autoBoardFlipEnabled, setAutoBoardFlipEnabled] = useState(
    !["online", "bot"].includes(session?.mode)
  );
  const [endgameMessage, setEndgameMessage] = useState("");
  const [showEndgameModal, setShowEndgameModal] = useState(false);
  const [clockTimeoutPending, setClockTimeoutPending] = useState(null);
  const [showLocalRestartChooser, setShowLocalRestartChooser] = useState(false);
  const [showResignConfirm, setShowResignConfirm] = useState(false);
  const [pendingLeaveDestination, setPendingLeaveDestination] = useState(null);
  const lastEndgameSignatureRef = useRef("");
  const moveTrackerRef = useRef({ gameId: "", moveCount: 0 });
  const handledAnalysisRetryRef = useRef(0);
  const gameSounds = useGameSounds(
    game,
    session?.color || game?.bot?.humanColor || null,
    pendingMove,
    startedWithBootstrapRef.current
  );

  useDocumentTitle(
    gameDocumentTitle(game, session?.color || game?.bot?.humanColor || null)
  );

  useNavigationBlocker(
    (destination) => {
      if (!shouldConfirmGameNavigation(gameRef.current)) return true;
      setPendingLeaveDestination(destination);
      return false;
    },
    shouldConfirmGameNavigation(game)
  );

  useEffect(() => {
    let cancelled = false;
    setCatalogError("");
    getCatalog()
      .then((payload) => {
        if (cancelled) return;
        setCatalog(payload);
      })
      .catch((requestError) => {
        if (cancelled) return;
        setCatalogError(requestError.message);
      });
    return () => {
      cancelled = true;
    };
  }, [catalogRetryKey]);

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
      setPendingMove((currentPending) => (
        currentPending && incoming.version > currentPending.baseVersion
          ? null
          : currentPending
      ));
      setInitialLoading(false);
    },
    [gameId]
  );

  const refreshGame = useCallback(async () => {
    const latest = await getGame(gameId, session?.token);
    applyIncomingGame(latest);

    if (!session) {
      const restoredSession = sessionForPublicGame(gameId, latest);
      if (restoredSession) {
        saveGameSession(gameId, restoredSession);
        setSession(restoredSession);
      }
    }

    return latest;
  }, [applyIncomingGame, gameId, session]);

  useEffect(() => {
    if (startedWithBootstrapRef.current) {
      onBootstrapConsumed?.(gameId);
      return undefined;
    }

    let cancelled = false;
    setInitialLoading(true);
    setError("");

    getGame(gameId, session?.token)
      .then((latest) => {
        if (cancelled) {
          return;
        }
        applyIncomingGame(latest);
        if (!session) {
          const restoredSession = sessionForPublicGame(gameId, latest);
          if (restoredSession) {
            saveGameSession(gameId, restoredSession);
            setSession(restoredSession);
          }
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          if (requestError instanceof ApiError && [404, 410].includes(requestError.status)) {
            forgetRecentGame(browserLocalStorage(), gameId);
          }
          setError(requestError.message);
          setInitialLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [applyIncomingGame, gameId, onBootstrapConsumed, session?.token]);

  const connectionStatus = useGameSocket({
    gameId,
    token: session?.token,
    enabled: Boolean(game),
    onGame: applyIncomingGame,
    onPresence: (payload) => setPresence(payload.connected || { white: false, black: false }),
    onEvent: (payload) => {
      if (payload.type === "player_joined") {
        setSocketMessage(`${colorLabel(payload.color)} joined the game.`);
      } else if (payload.type === "bot_error") {
        gameSounds.play("error");
        setError(payload.message || "The chess bot is temporarily unavailable.");
        setAnalysisRefreshing(false);
      } else if (
        payload.type === "match_analysis"
        && matchAnalysisEnabled
        && analysisMatchesGame(payload.analysis, gameRef.current)
      ) {
        setMatchAnalysis(payload.analysis);
        setAnalysisRefreshing(false);
      }
    },
    onError: setSocketMessage,
  });
  const connectionStatusRef = useRef(connectionStatus);
  connectionStatusRef.current = connectionStatus;

  useEffect(() => {
    if (!botTurnIsPending(game)) {
      return undefined;
    }

    let cancelled = false;
    let pollTimer;
    const pollBotState = async () => {
      try {
        await refreshGame();
      } catch {
        // The WebSocket may still deliver the move; retry without disrupting play.
      } finally {
        if (!cancelled) {
          pollTimer = window.setTimeout(
            pollBotState,
            fallbackPollDelayMs("botTurn", connectionStatusRef.current)
          );
        }
      }
    };

    pollTimer = window.setTimeout(
      pollBotState,
      fallbackPollDelayMs("botTurn", connectionStatusRef.current)
    );
    return () => {
      cancelled = true;
      window.clearTimeout(pollTimer);
    };
  }, [
    game?.bot?.status,
    game?.currentPlayer,
    game?.id,
    game?.phase,
    game?.version,
    refreshGame,
  ]);

  const recentGameColor = session?.color || game?.bot?.humanColor || null;
  const recentGameFinished = Boolean(
    game && (game.phase === "finished" || FINISHED_STATUSES.has(game.gameStatus) || game.winner)
  );
  useEffect(() => {
    if (!game?.id) return;
    recordRecentGame(browserLocalStorage(), {
      gameId: game.id,
      mode: game.mode,
      variant: game.variant,
      color: recentGameColor,
      finished: recentGameFinished,
    });
  }, [game?.id, game?.mode, game?.variant, game?.version, recentGameColor, recentGameFinished]);

  const activeOnlineInviteState = useMemo(
    () => onlineInviteState({
      mode: game?.mode,
      gameReady: game?.ready,
      playerColor: session?.color,
      playerRole: session?.role,
      presence,
      connectionStatus,
    }),
    [
      connectionStatus,
      game?.mode,
      game?.ready,
      presence,
      session?.color,
      session?.role,
    ]
  );

  useEffect(() => {
    if (!matchAnalysisEnabled || !game?.configuration?.matchPredictorEnabled) {
      setMatchAnalysis(null);
      setAnalysisRefreshing(false);
      return undefined;
    }
    if (botTurnIsPending(game)) {
      setMatchAnalysis(null);
      setAnalysisRefreshing(true);
      return undefined;
    }

    let cancelled = false;
    let pollTimer;
    let automaticRetries = 0;
    const forceInitialRetry = analysisRetryKey !== handledAnalysisRetryRef.current;
    if (forceInitialRetry) {
      handledAnalysisRetryRef.current = analysisRetryKey;
    }
    setAnalysisRefreshing(true);
    setMatchAnalysis((current) => (current?.gameId === game.id ? current : null));
    const queueTransientRetry = () => {
      if (automaticRetries >= 2) return;
      automaticRetries += 1;
      pollTimer = window.setTimeout(() => {
        if (cancelled) return;
        setMatchAnalysis(null);
        setAnalysisRefreshing(true);
        loadAnalysis();
      }, 4000);
    };
    const loadAnalysis = (forceRetry = false) => {
      getMatchAnalysis(game.id, session?.token, { retry: forceRetry })
        .then((analysis) => {
          if (cancelled || !analysisMatchesGame(analysis, gameRef.current)) return;
          if (analysis.status === "analyzing") {
            setMatchAnalysis((current) => current || analysis);
            pollTimer = window.setTimeout(
              loadAnalysis,
              fallbackPollDelayMs("analysis", connectionStatusRef.current)
            );
            return;
          }
          setMatchAnalysis(analysis);
          setAnalysisRefreshing(false);
          if (analysis.status === "unavailable") queueTransientRetry();
        })
        .catch((requestError) => {
          if (cancelled) return;
          setMatchAnalysis({
            gameId: game.id,
            gameVersion: game.version,
            enabled: true,
            eligible: true,
            status: "unavailable",
            reason: requestError.message,
          });
          setAnalysisRefreshing(false);
          queueTransientRetry();
        });
    };
    loadAnalysis(forceInitialRetry);

    return () => {
      cancelled = true;
      window.clearTimeout(pollTimer);
    };
  }, [
    analysisRetryKey,
    game?.configuration?.matchPredictorEnabled,
    game?.id,
    game?.version,
    matchAnalysisEnabled,
    session?.token,
  ]);

  const retryMatchAnalysis = useCallback(() => {
    setMatchAnalysis(null);
    setAnalysisRefreshing(true);
    setAnalysisRetryKey((current) => current + 1);
  }, []);

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
  const canResign = Boolean(
    game?.ready
    && game?.phase === "play"
    && !FINISHED_STATUSES.has(game?.gameStatus)
    && !game?.winner
    && (game?.mode === "local" || session?.color)
  );
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

  const visibleGame = useMemo(
    () => projectPendingMove(
      historyGame,
      pendingMove?.move,
      pendingMove?.promotion,
      pendingMove?.submittedAtMs
    ),
    [historyGame, pendingMove]
  );

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
      gameSounds.play("error");
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
    if (!["online", "bot"].includes(game?.mode) || !session?.color) {
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
      setBoardFlipped(
        ["online", "bot"].includes(game.mode) ? session?.color === "black" : false
      );
      setAutoBoardFlipEnabled(!["online", "bot"].includes(game.mode));
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
      !visibleGame?.clock ||
      visibleGame.phase !== "play" ||
      FINISHED_STATUSES.has(visibleGame.gameStatus)
    ) {
      return undefined;
    }

    const activeColor = visibleGame.clock.activeColor;
    const deadlineSignature = [
      visibleGame.id,
      visibleGame.version,
      activeColor,
      visibleGame.clock.turnStartedAt,
    ].join(":");
    setClockTimeoutPending((current) => (
      current?.signature === deadlineSignature ? current : null
    ));
    const refreshDelay = clockDeadlineDelayMs(visibleGame.clock);
    if (refreshDelay == null) return undefined;
    const timer = window.setTimeout(() => {
      const current = gameRef.current;
      if (
        current?.id === visibleGame.id
        && current.version === visibleGame.version
        && current.clock?.activeColor === activeColor
      ) {
        setClockTimeoutPending({
          signature: deadlineSignature,
          expiredColor: activeColor,
        });
      }
      refreshGame().catch((requestError) => {
        gameSounds.play("error");
        setError(requestError.message);
      });
    }, Math.max(0, refreshDelay));
    return () => window.clearTimeout(timer);
  }, [
    visibleGame?.clock?.activeColor,
    visibleGame?.clock?.remainingSeconds,
    visibleGame?.clock?.turnStartedAt,
    visibleGame?.gameStatus,
    visibleGame?.id,
    visibleGame?.phase,
    visibleGame?.version,
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
    setClockTimeoutPending(null);
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
      gameSounds.play("error");
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

  const submitMove = async (fromSquare, toSquare, promotion = null, moveOption = null) => {
    const current = gameRef.current;
    const previewMove = moveOption || current?.validMoves.find(
      (move) =>
        move.from.row === fromSquare.row &&
        move.from.col === fromSquare.col &&
        move.to.row === toSquare.row &&
        move.to.col === toSquare.col
    );
    const pendingId = pendingMoveIdRef.current + 1;
    pendingMoveIdRef.current = pendingId;
    if (current && previewMove) {
      const movingPiece = current.board?.[fromSquare.row]?.[fromSquare.col];
      setPendingMove({
        id: pendingId,
        baseVersion: current.version,
        move: previewMove,
        pieceType: movingPiece?.type || null,
        promotion,
        submittedAtMs: Date.now(),
      });
      setSelectedSquare(null);
    }
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
    } finally {
      setPendingMove((currentPending) => (
        currentPending?.id === pendingId ? null : currentPending
      ));
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
        setPendingPromotion({ from: selectedSquare, to: { row, col }, move: chosenMove });
      } else {
        submitMove(selectedSquare, { row, col }, null, chosenMove);
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
      } else if (game.mode === "bot") {
        setBoardFlipped(game.bot?.humanColor === "black");
      } else if (action === "accept") {
        setBoardFlipped(false);
      }
    } catch {
      // The shared error banner explains restart failures.
    }
  };

  const handleDrawOffer = async (action, color) => {
    try {
      await runAction(() => mutate(respondToDraw, { action, color }));
    } catch {
      // The shared error banner explains why the draw action was refused.
    }
  };

  const handleResign = async (color = null) => {
    try {
      await runAction(() => mutate(resignGame, color ? { color } : {}));
      setShowResignConfirm(false);
    } catch {
      // The shared error banner explains why the resignation was refused.
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

  const handleGameNavigation = (destination) => {
    if (shouldConfirmGameNavigation(game)) {
      setPendingLeaveDestination(destination);
      return;
    }
    navigate(destination);
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
    return <PageSkeleton variant="play" />;
  }

  if (!game) {
    return (
      <div className="app-shell centered">
        <div className="loading-card">
          <h1>Game unavailable</h1>
          <p>{error || "This game could not be loaded."}</p>
          <div className="button-row">
            <Button onClick={() => window.location.reload()}>
              Try again
            </Button>
            <Button variant="secondary" onClick={() => navigate("/")}>
              Back home
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell page-frame">
      <TopNav
        onReset={handleRestartRequest}
        onResign={() => setShowResignConfirm(true)}
        canResign={canResign}
        onOfferDraw={() => handleDrawOffer(
          "offer",
          game.mode === "local" ? game.currentPlayer : session?.color
        )}
        canOfferDraw={canResign && game.mode !== "bot" && !game.drawOfferedBy}
        onHome={() => handleGameNavigation("/")}
        onCustomize={() => handleGameNavigation("/customize")}
        currentPlayer={game.currentPlayer}
        gameStatus={game.gameStatus}
        winner={game.winner}
        onFlipBoard={() => setBoardFlipped((current) => !current)}
        onToggleAutoBoardFlip={() => setAutoBoardFlipEnabled((current) => !current)}
        autoBoardFlipEnabled={autoBoardFlipEnabled}
        onToggleMatchAnalysis={() => setMatchAnalysisEnabled((current) => !current)}
        matchAnalysisEnabled={matchAnalysisEnabled}
        matchAnalysisAvailable={game.configuration?.matchPredictorEnabled !== false}
        canReset={canRequestRestart}
        mode={game.mode}
        playerColor={session?.color}
        presence={presence}
        gameReady={game.ready}
        variant={game.variant}
        phase={game.phase}
        bot={game.bot}
        soundVolume={gameSounds.volume}
        soundMuted={gameSounds.muted}
        onSoundVolumeChange={gameSounds.setVolume}
        onToggleSoundMuted={gameSounds.toggleMuted}
      />

      {game.mode === "online" ? (
        <OnlineLobby
          session={session}
          inviteState={activeOnlineInviteState}
          returnUrl={new URL(`/game/${encodeURIComponent(gameId)}`, window.location.origin).href}
          onReplaceInvite={handleReplaceInvite}
        />
      ) : null}

      {error ? <p className="global-error">{error}</p> : null}
      {socketMessage ? <p className="sync-message">{socketMessage}</p> : null}
      <StableStatus
        className="global-loading"
        visible={actionLoading || botTurnIsPending(game)}
        message={
          botTurnIsPending(game)
            ? `${game.bot?.label || "Chess"} bot is thinking...`
            : actionLoading
              ? pendingMove
                ? "Confirming move..."
                : "Syncing authoritative game state..."
              : ""
        }
      />
      <DrawOfferPanel
        game={game}
        playerColor={session?.color}
        onRespond={handleDrawOffer}
        actionLoading={actionLoading}
      />
      <RestartRequestPanel
        game={game}
        playerColor={session?.color}
        onRespond={handleRematch}
        actionLoading={actionLoading}
      />
      {game.phase === "ability_selection" ? (
        <AbilitySelectionPage
          game={game}
          catalog={catalog}
          catalogError={catalogError}
          onRetryCatalog={() => setCatalogRetryKey((current) => current + 1)}
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
          game={visibleGame}
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
          matchAnalysis={matchAnalysis}
          analysisRefreshing={analysisRefreshing}
          onRetryAnalysis={retryMatchAnalysis}
          matchAnalysisEnabled={matchAnalysisEnabled}
          playerColor={
            ["online", "bot"].includes(game.mode)
              ? session?.color || game.bot?.humanColor || null
              : null
          }
        />
      ) : (
        <PlayPage
          game={visibleGame}
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
          matchAnalysis={matchAnalysis}
          analysisRefreshing={analysisRefreshing}
          onRetryAnalysis={retryMatchAnalysis}
          matchAnalysisEnabled={matchAnalysisEnabled}
          playerColor={
            ["online", "bot"].includes(game.mode)
              ? session?.color || game.bot?.humanColor || null
              : null
          }
        />
      )}

      <SiteFooter />

      {pendingPromotion ? (
        <Dialog
          open
          onClose={() => setPendingPromotion(null)}
          closeLabel="Close Pawn action dialog"
          eyebrow="Final rank reached"
          title="Choose a Pawn action"
          description={
            playerHasAbility(game, game.currentPlayer, "kamikaze")
              ? "Promote normally, or detonate it with your Kamikaze ability."
              : "Choose the piece this Pawn becomes."
          }
          actions={(
            <Button variant="secondary" onClick={() => setPendingPromotion(null)}>
              Cancel
            </Button>
          )}
        >
          <div className="promotion-options">
              {["queen", "rook", "bishop", "knight"].map((pieceType) => (
                <Button
                  key={pieceType}
                  onClick={() => {
                    const pending = pendingPromotion;
                    setPendingPromotion(null);
                    submitMove(pending.from, pending.to, pieceType, pending.move);
                  }}
                >
                  {colorLabel(pieceType)}
                </Button>
              ))}
              {playerHasAbility(game, game.currentPlayer, "kamikaze") ? (
                <Button
                  className="kamikaze-choice"
                  onClick={() => {
                    const pending = pendingPromotion;
                    setPendingPromotion(null);
                    submitMove(pending.from, pending.to, "kamikaze", pending.move);
                  }}
                >
                  ✹ Kamikaze
                </Button>
              ) : null}
          </div>
        </Dialog>
      ) : null}

      {pendingLeaveDestination ? (
        <Dialog
          open
          onClose={() => setPendingLeaveDestination(null)}
          closeLabel="Close leave game confirmation"
          eyebrow="Current game"
          title="Leave this game?"
          description={`Leave this game and go to ${navigationDestination(pendingLeaveDestination).destination}? The game stays open, and you can return to it from Home.`}
          className="leave-game-dialog"
          actions={(
            <>
              <Button variant="secondary" onClick={() => setPendingLeaveDestination(null)}>
                Stay in game
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  const destination = pendingLeaveDestination;
                  setPendingLeaveDestination(null);
                  navigate(destination, { bypassBlocker: true });
                }}
              >
                {navigationDestination(pendingLeaveDestination).leaveLabel}
              </Button>
            </>
          )}
        />
      ) : null}

      {showResignConfirm && canResign ? (
        <Dialog
          open
          onClose={() => setShowResignConfirm(false)}
          closeLabel="Close resign confirmation"
          title={game.mode === "local" ? "Who is resigning?" : "Resign this game?"}
          description={
            game.mode === "local"
              ? "The other side will be declared the winner. This cannot be undone."
              : "Your opponent will be declared the winner. This cannot be undone."
          }
          actions={(
            <>
              <Button variant="secondary" onClick={() => setShowResignConfirm(false)}>
                Keep playing
              </Button>
              {game.mode === "local" ? ["white", "black"].map((color) => (
                <Button
                  key={color}
                  variant="danger"
                  disabled={actionLoading}
                  onClick={() => handleResign(color)}
                >
                  {colorLabel(color)} resigns
                </Button>
              )) : (
                <Button variant="danger" disabled={actionLoading} onClick={() => handleResign()}>
                  Resign
                </Button>
              )}
            </>
          )}
        />
      ) : null}

      {showLocalRestartChooser ? (
        <Dialog
          open
          onClose={() => setShowLocalRestartChooser(false)}
          closeLabel="Close restart request dialog"
          eyebrow="Same-device approval"
          title="Who is requesting?"
          description="The other player must approve before the board resets."
          actions={(
            <>
              {["white", "black"].map((color) => (
                <Button key={color} disabled={actionLoading} onClick={() => handleRematch("request", color)}>
                  {colorLabel(color)} requests restart
                </Button>
              ))}
              <Button variant="secondary" onClick={() => setShowLocalRestartChooser(false)}>
                Cancel
              </Button>
            </>
          )}
        />
      ) : null}

      {clockTimeoutPending && !FINISHED_STATUSES.has(game.gameStatus) && !game.winner ? (
        <Dialog
          open
          onClose={() => setClockTimeoutPending(null)}
          closeLabel="Close timeout confirmation"
          eyebrow="Clock reached zero"
          title={`${colorLabel(oppositeColor(clockTimeoutPending.expiredColor))} won on time`}
          description={`${colorLabel(clockTimeoutPending.expiredColor)} ran out of time. Saving the final result...`}
          ariaLive="assertive"
        />
      ) : showEndgameModal ? (
        <Dialog
          open
          onClose={() => setShowEndgameModal(false)}
          closeLabel="Close match result"
          eyebrow="Final position"
          title="Match finished"
          description={endgameMessage}
          ariaLive="polite"
          actions={(
            <>
              {canRequestRestart ? (
                <Button onClick={handleRestartRequest}>
                  {game.mode === "bot" ? "Play again" : "Request a rematch"}
                </Button>
              ) : null}
              <Button variant="secondary" onClick={customizeCurrentGame}>
                Customize this game
              </Button>
              <Button variant="secondary" onClick={() => navigate("/")}>
                Home
              </Button>
              <Button variant="secondary" onClick={() => setShowEndgameModal(false)}>
                Review board
              </Button>
            </>
          )}
        />
      ) : null}
    </div>
  );
}

function App() {
  const route = useRoute();
  const bootstrapGamesRef = useRef(new Map());
  const handleBootstrapConsumed = useCallback((gameId) => {
    bootstrapGamesRef.current.delete(gameId);
  }, []);

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
    bootstrapGamesRef.current.set(response.game.id, response.game);
    // A successful launch intentionally consumes the Customize draft.
    customizeSession.clear();
    navigate(`/game/${response.game.id}`, { bypassBlocker: true });
  };

  const handleJoin = async (inviteToken) => {
    const response = await joinGame(inviteToken);
    const session = sessionFromResponse(response);
    saveGameSession(response.game.id, session);
    bootstrapGamesRef.current.set(response.game.id, response.game);
    navigate(`/game/${response.game.id}`, { replace: true });
  };

  const handleScanImport = async (payload) => {
    const response = await importScannedGame(payload);
    saveGameSession(response.game.id, sessionFromResponse(response));
    bootstrapGamesRef.current.set(response.game.id, response.game);
    navigate(`/game/${response.game.id}`, { bypassBlocker: true });
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
    return (
      <GameWorkspace
        key={route.gameId}
        gameId={route.gameId}
        initialGame={bootstrapGamesRef.current.get(route.gameId) || null}
        onBootstrapConsumed={handleBootstrapConsumed}
      />
    );
  }

  if (route.name === "customize") {
    return (
      <Suspense fallback={<PageSkeleton variant="customize" />}>
        <CustomizePage
          onCreate={handleCreate}
          onHome={() => navigate("/")}
          initialPreset={route.preset}
        />
      </Suspense>
    );
  }

  if (route.name === "rulebook") {
    return (
      <Suspense fallback={<PageSkeleton variant="rulebook" />}>
        <RulebookPage
          onHome={() => navigate("/")}
          onCustomize={() => navigate(customizeSession.returnPath())}
        />
      </Suspense>
    );
  }

  if (route.name === "scanner") {
    return (
      <Suspense fallback={<PageSkeleton variant="rulebook" />}>
        <ScannerPage
          onImport={handleScanImport}
          onHome={() => navigate("/")}
          onCustomize={() => navigate(customizeSession.returnPath())}
        />
      </Suspense>
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
