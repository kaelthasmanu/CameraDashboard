import { useEffect, useState } from 'react';
import { api } from '../../../shared/lib/api-client';

const POLL_INTERVAL_MS = 1_000;
const WS_RETRY_MS = 2_000;
const DETECTION_TTL_MS = 2_000;

function websocketUrl() {
  const apiUrl = new URL(import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1');
  apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  apiUrl.pathname = `${apiUrl.pathname.replace(/\/$/, '')}/person-detections/ws`;
  apiUrl.search = '';
  const token = localStorage.getItem('access_token');
  if (token) apiUrl.searchParams.set('token', token);
  return apiUrl.toString();
}

export function usePersonDetections(userId: number | undefined) {
  const [detectedCameraIds, setDetectedCameraIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (userId === undefined) return;
    let disposed = false;
    const expiryTimers = new Map<number, number>();
    let socket: WebSocket | undefined;
    let retryTimer: number | undefined;

    const clearCamera = (cameraId: number) => {
      window.clearTimeout(expiryTimers.get(cameraId));
      expiryTimers.delete(cameraId);
      setDetectedCameraIds(current => {
        if (!current.has(cameraId)) return current;
        const next = new Set(current);
        next.delete(cameraId);
        return next;
      });
    };

    const markDetected = (cameraId: number) => {
      window.clearTimeout(expiryTimers.get(cameraId));
      expiryTimers.set(cameraId, window.setTimeout(() => clearCamera(cameraId), DETECTION_TTL_MS));
      setDetectedCameraIds(current => current.has(cameraId) ? current : new Set(current).add(cameraId));
    };

    const load = async () => {
      try {
        const detections = await api.personDetections();
        if (disposed) return;
        const activeIds = new Set(detections.map(detection => detection.camera_id));
        activeIds.forEach(markDetected);
        setDetectedCameraIds(current => {
          const next = new Set([...current].filter(cameraId => activeIds.has(cameraId)));
          activeIds.forEach(cameraId => next.add(cameraId));
          return next;
        });
      } catch {
        if (!disposed) setDetectedCameraIds(new Set());
      }
    };
    void load();
    const interval = window.setInterval(() => void load(), POLL_INTERVAL_MS);

    const connect = () => {
      if (disposed || !localStorage.getItem('access_token')) return;
      socket = new WebSocket(websocketUrl());
      socket.onmessage = event => {
        try {
          const message = JSON.parse(event.data) as { type?: string; camera_id?: number };
          if (typeof message.camera_id !== 'number') return;
          if (message.type === 'person_detection') markDetected(message.camera_id);
          if (message.type === 'person_cleared') clearCamera(message.camera_id);
        } catch {
          // Ignore malformed events and keep the connection alive.
        }
      };
      socket.onclose = () => {
        if (!disposed) retryTimer = window.setTimeout(connect, WS_RETRY_MS);
      };
      socket.onerror = () => socket?.close();
    };
    connect();

    return () => {
      disposed = true;
      window.clearInterval(interval);
      window.clearTimeout(retryTimer);
      expiryTimers.forEach(timer => window.clearTimeout(timer));
      socket?.close();
    };
  }, [userId]);

  return detectedCameraIds;
}