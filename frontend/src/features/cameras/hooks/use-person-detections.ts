import { useEffect, useState } from 'react';
import { api } from '../../../shared/lib/api-client';

const POLL_INTERVAL_MS = 1_000;

export function usePersonDetections(userId: number | undefined) {
  const [detectedCameraIds, setDetectedCameraIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (userId === undefined) return;
    let disposed = false;
    const load = async () => {
      try {
        const detections = await api.personDetections();
        if (!disposed) setDetectedCameraIds(new Set(detections.map(detection => detection.camera_id)));
      } catch {
        if (!disposed) setDetectedCameraIds(new Set());
      }
    };
    void load();
    const interval = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => { disposed = true; window.clearInterval(interval); };
  }, [userId]);

  return detectedCameraIds;
}