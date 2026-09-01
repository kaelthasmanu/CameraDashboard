import { useEffect, useRef, useState, type RefObject } from 'react';

const SAMPLE_INTERVAL_MS = 100;
const ALARM_COOLDOWN_MS = 4_000;
const MOTION_THRESHOLD = 0.025;
const PIXEL_DIFFERENCE = 18;
const SAMPLE_WIDTH = 32;
const SAMPLE_HEIGHT = 18;

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

function hasMotion(previous: Uint8ClampedArray, current: Uint8ClampedArray) {
  let changedPixels = 0;
  for (let index = 0; index < current.length; index += 4) {
    const difference = Math.abs(current[index] - previous[index])
      + Math.abs(current[index + 1] - previous[index + 1])
      + Math.abs(current[index + 2] - previous[index + 2]);
    if (difference > PIXEL_DIFFERENCE) changedPixels += 1;
  }
  return changedPixels / (current.length / 4) > MOTION_THRESHOLD;
}

export function useMotionAlarm(videoRef: RefObject<HTMLVideoElement | null>, enabled: boolean, personDetected = false) {
  const [motionDetected, setMotionDetected] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!enabled) {
      setMotionDetected(false);
      return undefined;
    }

    const video = videoRef.current;
    if (!video) return undefined;

    const canvas = document.createElement('canvas');
    canvas.width = SAMPLE_WIDTH;
    canvas.height = SAMPLE_HEIGHT;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) return undefined;

    let previousFrame: Uint8ClampedArray | null = null;
    let lastAlarmAt = 0;
    let motionResetTimer: number | undefined;

    const unlockAudio = () => {
      audioContextRef.current ??= getAudioContext();
      void audioContextRef.current?.resume();
    };
    document.addEventListener('pointerdown', unlockAudio, { once: true });
    document.addEventListener('keydown', unlockAudio, { once: true });

    const sample = () => {
      if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || video.videoWidth === 0) return;
      try {
        context.drawImage(video, 0, 0, SAMPLE_WIDTH, SAMPLE_HEIGHT);
        const currentFrame = context.getImageData(0, 0, SAMPLE_WIDTH, SAMPLE_HEIGHT).data;
        if (previousFrame && (hasMotion(previousFrame, currentFrame) || personDetected)) {
          setMotionDetected(true);
          window.clearTimeout(motionResetTimer);
          motionResetTimer = window.setTimeout(() => setMotionDetected(false), ALARM_COOLDOWN_MS);
          if (Date.now() - lastAlarmAt >= ALARM_COOLDOWN_MS) {
            lastAlarmAt = Date.now();
            const audioContext = audioContextRef.current;
            if (audioContext?.state === 'running') playAlarm(audioContext);
          }
        }
        previousFrame = currentFrame;
      } catch {
        // Canvas access can fail transiently while a WebRTC track is changing.
        previousFrame = null;
      }
    };

    const interval = window.setInterval(sample, SAMPLE_INTERVAL_MS);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(motionResetTimer);
      document.removeEventListener('pointerdown', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
  }, [enabled, personDetected, videoRef]);

  return motionDetected;
}