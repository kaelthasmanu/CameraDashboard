import { useEffect, useRef, useState } from 'react';

const ALARM_COOLDOWN_MS = 4_000;

type AudioContextConstructor = typeof AudioContext;

function getAudioContext() {
  const Context = (window.AudioContext || (window as Window & { webkitAudioContext?: AudioContextConstructor }).webkitAudioContext);
  return Context ? new Context() : null;
}

function playAlarm(audioContext: AudioContext) {
  const now = audioContext.currentTime;
  const oscillator = audioContext.createOscillator();
  const gain = audioContext.createGain();
  oscillator.type = 'square';
  oscillator.frequency.setValueAtTime(880, now);
  oscillator.frequency.setValueAtTime(660, now + 0.18);
  oscillator.frequency.setValueAtTime(880, now + 0.36);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.12, now + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.55);
  oscillator.connect(gain).connect(audioContext.destination);
  oscillator.start(now);
  oscillator.stop(now + 0.6);
}

export function usePersonAlarm(enabled: boolean, personDetected: boolean, soundEnabled = true) {
  const [personAlarmActive, setPersonAlarmActive] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!enabled) {
      setPersonAlarmActive(false);
      return undefined;
    }

    const unlockAudio = () => {
      audioContextRef.current ??= getAudioContext();
      void audioContextRef.current?.resume();
    };
    document.addEventListener('pointerdown', unlockAudio);
    document.addEventListener('keydown', unlockAudio);
    return () => {
      document.removeEventListener('pointerdown', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !personDetected) {
      setPersonAlarmActive(false);
      return undefined;
    }

    setPersonAlarmActive(true);
    const triggerAlarm = () => {
      if (!soundEnabled) return;
      const audioContext = audioContextRef.current;
      if (audioContext?.state === 'running') playAlarm(audioContext);
    };
    triggerAlarm();
    const interval = window.setInterval(triggerAlarm, ALARM_COOLDOWN_MS);
    return () => window.clearInterval(interval);
  }, [enabled, personDetected, soundEnabled]);

  return personAlarmActive;
}