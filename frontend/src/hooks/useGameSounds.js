import { useCallback, useEffect, useRef, useState } from "react";

import {
  DEFAULT_SOUND_VOLUME,
  SOUND_ASSETS,
  clampSoundVolume,
  gameSoundSnapshot,
  readSoundPreferences,
  soundForGameTransition,
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
    return [name, audio];
  }));
}

export default function useGameSounds(game, playerColor) {
  const [preferences, setPreferences] = useState(() => (
    readSoundPreferences(browserStorage())
  ));
  const audioElementsRef = useRef({});
  const gameSnapshotRef = useRef(null);

  useEffect(() => {
    audioElementsRef.current = createAudioElements();
    return () => {
      Object.values(audioElementsRef.current).forEach((audio) => {
        audio.pause();
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

  const playSound = useCallback((name) => {
    if (preferences.muted || preferences.volume === 0) return;
    const audio = audioElementsRef.current[name];
    if (!audio) return;
    try {
      audio.pause();
      audio.currentTime = 0;
      const playback = audio.play();
      playback?.catch(() => {});
    } catch {
      // Browsers may reject playback until the page receives a user gesture.
    }
  }, [preferences.muted, preferences.volume]);

  useEffect(() => {
    const currentSnapshot = gameSoundSnapshot(game, playerColor);
    const sound = soundForGameTransition(gameSnapshotRef.current, currentSnapshot);
    gameSnapshotRef.current = currentSnapshot;
    if (sound) playSound(sound);
  }, [game, playerColor, playSound]);

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
    setVolume,
    toggleMuted,
  };
}
