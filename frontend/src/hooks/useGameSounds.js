import { useCallback, useEffect, useRef, useState } from "react";

import {
  DEFAULT_SOUND_VOLUME,
  SOUND_ASSETS,
  clampSoundVolume,
  clockSoundPlan,
  confirmsOptimisticMove,
  gameSoundSnapshot,
  optimisticMoveSoundToken,
  readSoundPreferences,
  soundsForGameTransition,
  writeSoundPreferences,
} from "../gameAudio";

function browserStorage() {
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function createAudioElements() {
  if (typeof globalThis.Audio !== "function") return {};
  return Object.fromEntries(Object.entries(SOUND_ASSETS).map(([name, source]) => {
    const audio = new globalThis.Audio(source);
    audio.preload = "auto";
    audio.load?.();
    return [name, audio];
  }));
}

export default function useGameSounds(
  game,
  playerColor,
  pendingMove = null,
  announceInitialStart = false
) {
  const [preferences, setPreferences] = useState(() => (
    readSoundPreferences(browserStorage())
  ));
  const audioElementsRef = useRef({});
  const gameSnapshotRef = useRef(null);
  const optimisticMoveSoundRef = useRef(null);
  const lastOptimisticMoveKeyRef = useRef("");
  const soundStopTimersRef = useRef(new Map());
  const clockScheduleTimersRef = useRef([]);
  const clockPlaybackRef = useRef(null);
  const firedClockWarningsRef = useRef(new Set());

  const stopSound = useCallback((name) => {
    const stopTimer = soundStopTimersRef.current.get(name);
    if (stopTimer != null) {
      globalThis.clearTimeout(stopTimer);
      soundStopTimersRef.current.delete(name);
    }
    const audio = audioElementsRef.current[name];
    if (!audio) return;
    try {
      audio.pause();
      audio.loop = false;
      audio.currentTime = 0;
    } catch {
      // Audio cleanup should never interrupt game interaction.
    }
  }, []);

  const playSound = useCallback((name, options = {}) => {
    if (preferences.muted || preferences.volume === 0) return false;
    const audio = audioElementsRef.current[name];
    if (!audio) return false;
    stopSound(name);
    try {
      audio.loop = Boolean(options.loop);
      const playback = audio.play();
      playback?.catch(() => {});
      if (Number(options.durationMs) > 0) {
        const timer = globalThis.setTimeout(
          () => stopSound(name),
          Number(options.durationMs)
        );
        soundStopTimersRef.current.set(name, timer);
      }
      return true;
    } catch {
      // Browsers may reject playback until the page receives a user gesture.
      return false;
    }
  }, [preferences.muted, preferences.volume, stopSound]);

  useEffect(() => {
    audioElementsRef.current = createAudioElements();
    return () => {
      clockScheduleTimersRef.current.forEach((timer) => globalThis.clearTimeout(timer));
      clockScheduleTimersRef.current = [];
      soundStopTimersRef.current.forEach((timer) => globalThis.clearTimeout(timer));
      soundStopTimersRef.current.clear();
      Object.values(audioElementsRef.current).forEach((audio) => {
        audio.pause();
        audio.loop = false;
        audio.removeAttribute("src");
      });
      audioElementsRef.current = {};
    };
  }, []);

  useEffect(() => {
    writeSoundPreferences(browserStorage(), preferences);
    Object.values(audioElementsRef.current).forEach((audio) => {
      audio.volume = preferences.volume;
      audio.muted = preferences.muted;
    });
  }, [preferences]);

  useEffect(() => {
    const currentSnapshot = gameSoundSnapshot(game, playerColor);
    const previousSnapshot = gameSnapshotRef.current;
    let sounds = soundsForGameTransition(previousSnapshot, currentSnapshot, {
      announceInitialStart,
    });
    let optimisticToken = optimisticMoveSoundRef.current;

    const optimisticMoveConfirmed = confirmsOptimisticMove(
      optimisticToken,
      previousSnapshot,
      currentSnapshot
    );
    if (optimisticMoveConfirmed) {
      const optimisticSounds = new Set(optimisticToken.cues || []);
      sounds = sounds.filter((sound) => !optimisticSounds.has(sound));
      optimisticToken = null;
    }

    gameSnapshotRef.current = currentSnapshot;
    sounds.forEach((sound) => playSound(sound));

    const pendingKey = pendingMove?.id == null || !currentSnapshot
      ? ""
      : `${currentSnapshot.gameId}:${pendingMove.id}`;
    if (pendingKey && pendingKey !== lastOptimisticMoveKeyRef.current) {
      const nextToken = optimisticMoveSoundToken(currentSnapshot, pendingMove);
      lastOptimisticMoveKeyRef.current = pendingKey;
      if (nextToken) {
        optimisticToken = nextToken;
        nextToken.cues.forEach((sound) => playSound(sound));
      }
    } else if (!pendingMove && optimisticToken && !optimisticMoveConfirmed) {
      // A rejected or interrupted optimistic move must not suppress a later move.
      optimisticToken = null;
    }

    optimisticMoveSoundRef.current = optimisticToken;
  }, [announceInitialStart, game, pendingMove, playerColor, playSound]);

  useEffect(() => {
    clockScheduleTimersRef.current.forEach((timer) => globalThis.clearTimeout(timer));
    clockScheduleTimersRef.current = [];

    const plan = clockSoundPlan(game);
    const previousPlayback = clockPlaybackRef.current;
    const activeClockKey = plan
      ? `${plan.gameId}:${plan.epoch}:${plan.activeColor}`
      : null;
    if (
      previousPlayback?.kind === "final"
      && previousPlayback.activeClockKey !== activeClockKey
    ) {
      stopSound("clock");
      clockPlaybackRef.current = null;
    }
    if (!plan) {
      stopSound("clock");
      clockPlaybackRef.current = null;
      return undefined;
    }

    const startFinalClock = (event) => {
      const remainingDurationMs = Math.max(
        0,
        Number(event.endAtMs) - Date.now()
      );
      if (remainingDurationMs === 0) return;
      const played = playSound("clock", {
        durationMs: remainingDurationMs,
        loop: true,
      });
      if (played) {
        clockPlaybackRef.current = {
          kind: "final",
          activeClockKey,
          warningKey: event.key,
        };
      }
    };

    plan.events.forEach((event) => {
      if (event.loop) {
        if (event.crossed) {
          if (event.activeDurationMs > 0) startFinalClock(event);
          return;
        }
        const timer = globalThis.setTimeout(() => {
          startFinalClock(event);
        }, event.delayMs);
        clockScheduleTimersRef.current.push(timer);
        return;
      }

      if (firedClockWarningsRef.current.has(event.key)) return;
      if (event.crossed) {
        // Do not replay one-shot warnings after reloads or between turns.
        firedClockWarningsRef.current.add(event.key);
        return;
      }
      const timer = globalThis.setTimeout(() => {
        firedClockWarningsRef.current.add(event.key);
        playSound("clock", { durationMs: event.durationMs });
      }, event.delayMs);
      clockScheduleTimersRef.current.push(timer);
    });

    return () => {
      clockScheduleTimersRef.current.forEach((timer) => globalThis.clearTimeout(timer));
      clockScheduleTimersRef.current = [];
      if (
        clockPlaybackRef.current?.kind === "final"
        && clockPlaybackRef.current.activeClockKey === activeClockKey
      ) {
        stopSound("clock");
        clockPlaybackRef.current = null;
      }
    };
  }, [
    game?.clock?.activeColor,
    game?.clock?.initialSeconds,
    game?.clock?.remainingSeconds?.black,
    game?.clock?.remainingSeconds?.white,
    game?.clock?.turnStartedAt,
    game?.gameStatus,
    game?.historyPagination?.epoch,
    game?.id,
    game?.phase,
    game?.winner,
    playSound,
    stopSound,
  ]);

  const setVolume = useCallback((value) => {
    const volume = clampSoundVolume(value);
    setPreferences({
      volume,
      muted: volume === 0,
    });
  }, []);

  const toggleMuted = useCallback(() => {
    setPreferences((current) => (
      current.muted && current.volume === 0
        ? { volume: DEFAULT_SOUND_VOLUME, muted: false }
        : { ...current, muted: !current.muted }
    ));
  }, []);

  return {
    volume: preferences.volume,
    muted: preferences.muted,
    play: playSound,
    setVolume,
    toggleMuted,
  };
}
