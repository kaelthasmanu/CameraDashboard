import { useEffect } from 'react';
import { api } from '../../../shared/lib/api-client';

const HEARTBEAT_INTERVAL_MS = 15_000;

const inMemorySessionIds = new Map<number, string>();

function createSessionId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  // Keep the fallback within the API's validated ID format and minimum length.
  return `tab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2).padEnd(16, '0')}`;
}

function getSessionId(userId: number) {
  const key = `watchtower_presence_session_${userId}`;

  try {
    const existing = window.sessionStorage.getItem(key);
    if (existing) return existing;

    const sessionId = createSessionId();
    window.sessionStorage.setItem(key, sessionId);
    return sessionId;
  } catch {
    const existing = inMemorySessionIds.get(userId);
    if (existing) return existing;
    const sessionId = createSessionId();
    inMemorySessionIds.set(userId, sessionId);
    return sessionId;
  }
}

/**
 * Reports one visible browser session every 15 seconds. The server owns the
 * timestamp, so its active/inactive decision does not depend on this device's clock.
 */
export function usePresenceHeartbeat(userId: number | undefined) {
  useEffect(() => {
    if (!userId) return;

    const sessionId = getSessionId(userId);
    let disposed = false;
    const send = (visible = document.visibilityState === 'visible', keepalive = false) => {
      if (disposed && !keepalive) return;
      void api.heartbeat(sessionId, visible, keepalive).catch(() => undefined);
    };

    send();
    const interval = window.setInterval(() => send(), HEARTBEAT_INTERVAL_MS);
    const onVisibilityChange = () => send(document.visibilityState === 'visible');
    const onPageHide = () => send(false, true);

    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('pagehide', onPageHide);

    return () => {
      disposed = true;
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('pagehide', onPageHide);
      send(false, true);
    };
  }, [userId]);
}
