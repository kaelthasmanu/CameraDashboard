import { useCallback, useEffect, useState, type RefObject } from 'react';

export type LiveStreamState = 'idle' | 'connecting' | 'reconnecting' | 'live' | 'unsupported';

interface UseWhepStreamOptions {
  enabled: boolean;
  streamUrl: string;
  videoRef: RefObject<HTMLVideoElement | null>;
}

interface WhepConnection {
  abortController: AbortController;
  candidates: RTCIceCandidate[];
  closed: boolean;
  createdAt: number;
  disconnectTimer?: number;
  firstFrameAt?: number;
  frameCallbackId?: number;
  lastFrameAt?: number;
  peer: RTCPeerConnection | null;
  remoteDescriptionAt?: number;
  sessionUrl: string | null;
  stream: MediaStream | null;
}

type FrameCallbackVideo = HTMLVideoElement & {
  cancelVideoFrameCallback?: (handle: number) => void;
  requestVideoFrameCallback?: (callback: () => void) => number;
};

const CONNECT_TIMEOUT_MS = 12_000;
const DISCONNECT_GRACE_MS = 3_000;
const FRAME_TIMEOUT_MS = 8_000;
const MAX_RETRY_DELAY_MS = 10_000;

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function parseQuotedParameter(value: string, name: string) {
  const match = value.match(new RegExp(`(?:^|;)\\s*${name}="((?:\\\\.|[^"])*)"`, 'i'));
  return match?.[1]?.replace(/\\(.)/g, '$1');
}

function parseIceServers(linkHeader: string | null): RTCIceServer[] {
  if (!linkHeader) return [];

  return linkHeader
    .split(/,(?=\s*<)/)
    .flatMap((link) => {
      const url = link.match(/<([^>]+)>/)?.[1];
      if (!url || !/rel="?ice-server"?/i.test(link)) return [];

      const username = parseQuotedParameter(link, 'username');
      const credential = parseQuotedParameter(link, 'credential');
      return [{
        urls: [url],
        ...(username && credential ? { username, credential, credentialType: 'password' as const } : {}),
      }];
    });
}

function makeCandidateFragment(description: RTCSessionDescription | null, candidates: RTCIceCandidate[]) {
  if (!description?.sdp || !candidates.length) return '';

  const mediaSections: Array<{ media: string; mid: string }> = [];
  let iceUfrag = '';
  let icePwd = '';

  for (const line of description.sdp.split(/\r?\n/)) {
    if (line.startsWith('m=')) mediaSections.push({ media: line.slice(2), mid: String(mediaSections.length) });
    if (line.startsWith('a=mid:') && mediaSections.length) mediaSections[mediaSections.length - 1].mid = line.slice('a=mid:'.length);
    if (!iceUfrag && line.startsWith('a=ice-ufrag:')) iceUfrag = line.slice('a=ice-ufrag:'.length);
    if (!icePwd && line.startsWith('a=ice-pwd:')) icePwd = line.slice('a=ice-pwd:'.length);
  }

  if (!iceUfrag || !icePwd) return '';

  const candidatesByMedia = new Map<number, RTCIceCandidate[]>();
  for (const candidate of candidates) {
    if (candidate.sdpMLineIndex === null || !candidate.candidate) continue;
    const current = candidatesByMedia.get(candidate.sdpMLineIndex) ?? [];
    current.push(candidate);
    candidatesByMedia.set(candidate.sdpMLineIndex, current);
  }

  let fragment = `a=ice-ufrag:${iceUfrag}\r\na=ice-pwd:${icePwd}\r\n`;
  for (const [index, mediaCandidates] of candidatesByMedia) {
    const media = mediaSections[index];
    if (!media) continue;
    fragment += `m=${media.media}\r\na=mid:${media.mid}\r\n`;
    for (const candidate of mediaCandidates) fragment += `a=${candidate.candidate}\r\n`;
  }

  return fragment;
}

function retryDelay(attempt: number) {
  return Math.min(1_000 * 2 ** Math.min(attempt - 1, 4), MAX_RETRY_DELAY_MS);
}

/**
 * Mantiene una sesión WebRTC/WHEP viva. WHEP usa HTTP para señalización y
 * WebRTC para los frames, por lo que no requiere un WebSocket adicional.
 */
export function useWhepStream({ enabled, streamUrl, videoRef }: UseWhepStreamOptions) {
  const [state, setState] = useState<LiveStreamState>('idle');
  const [restartKey, setRestartKey] = useState(0);
  const reconnect = useCallback(() => setRestartKey((value) => value + 1), []);

  useEffect(() => {
    const video = videoRef.current;
    if (!enabled || !streamUrl || !video) {
      setState('idle');
      return undefined;
    }

    if (!('RTCPeerConnection' in window)) {
      setState('unsupported');
      return undefined;
    }

    let disposed = false;
    let retryAttempt = 0;
    let retryTimer: number | undefined;
    let activeConnection: WhepConnection | null = null;

    const isCurrent = (connection: WhepConnection) => !disposed && !connection.closed && activeConnection === connection;

    const releaseSession = (sessionUrl: string) => {
      void fetch(sessionUrl, { method: 'DELETE', keepalive: true }).catch(() => undefined);
    };

    const stopConnection = (connection = activeConnection) => {
      if (!connection || connection.closed) return;
      connection.closed = true;

      if (connection.disconnectTimer !== undefined) window.clearTimeout(connection.disconnectTimer);
      const frameVideo = video as FrameCallbackVideo;
      if (connection.frameCallbackId !== undefined) frameVideo.cancelVideoFrameCallback?.(connection.frameCallbackId);

      connection.abortController.abort();
      if (connection.peer) {
        connection.peer.onconnectionstatechange = null;
        connection.peer.oniceconnectionstatechange = null;
        connection.peer.onicecandidate = null;
        connection.peer.ontrack = null;
        connection.peer.close();
      }
      if (connection.sessionUrl) releaseSession(connection.sessionUrl);

      if (video.srcObject === connection.stream) {
        video.pause();
        video.srcObject = null;
      }
      if (activeConnection === connection) activeConnection = null;
    };

    const scheduleRetry = (immediate = false) => {
      if (disposed || retryTimer !== undefined) return;
      stopConnection();
      retryAttempt += 1;
      setState('reconnecting');
      retryTimer = window.setTimeout(() => {
        retryTimer = undefined;
        void startConnection();
      }, immediate ? 0 : retryDelay(retryAttempt));
    };

    const markFrameReceived = (connection: WhepConnection) => {
      if (!isCurrent(connection) || !connection.stream || video.srcObject !== connection.stream) return;
      const now = Date.now();
      connection.firstFrameAt ??= now;
      connection.lastFrameAt = now;
      retryAttempt = 0;
      setState('live');
    };

    const observeFrames = (connection: WhepConnection) => {
      const frameVideo = video as FrameCallbackVideo;
      if (!frameVideo.requestVideoFrameCallback) return;

      const observe = () => {
        connection.frameCallbackId = frameVideo.requestVideoFrameCallback?.(() => {
          markFrameReceived(connection);
          if (isCurrent(connection)) observe();
        });
      };
      observe();
    };

    const flushCandidates = (connection: WhepConnection) => {
      if (!isCurrent(connection) || !connection.remoteDescriptionAt || !connection.sessionUrl || !connection.peer?.localDescription || !connection.candidates.length) return;

      const candidates = connection.candidates.splice(0);
      const body = makeCandidateFragment(connection.peer.localDescription, candidates);
      if (!body) return;

      void fetch(connection.sessionUrl, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/trickle-ice-sdpfrag', 'If-Match': '*' },
        body,
        signal: connection.abortController.signal,
      })
        .then((response) => {
          if (!response.ok && response.status !== 204) throw new Error(`WHEP ICE ${response.status}`);
        })
        .catch((error: unknown) => {
          if (isCurrent(connection) && !isAbortError(error)) scheduleRetry();
        });
    };

    async function requestIceServers(connection: WhepConnection) {
      try {
        const response = await fetch(streamUrl, {
          method: 'OPTIONS',
          cache: 'no-store',
          signal: connection.abortController.signal,
        });
        return response.ok ? parseIceServers(response.headers.get('Link')) : [];
      } catch (error) {
        if (isAbortError(error)) throw error;
        // Los servidores WHEP antiguos pueden no implementar OPTIONS; aún se
        // puede establecer una sesión usando los candidatos locales.
        return [];
      }
    }

    async function startConnection() {
      if (disposed) return;

      stopConnection();
      const connection: WhepConnection = {
        abortController: new AbortController(),
        candidates: [],
        closed: false,
        createdAt: Date.now(),
        peer: null,
        sessionUrl: null,
        stream: null,
      };
      activeConnection = connection;
      setState(retryAttempt ? 'reconnecting' : 'connecting');

      try {
        const iceServers = await requestIceServers(connection);
        if (!isCurrent(connection)) return;

        const peer = new RTCPeerConnection({ iceServers });
        connection.peer = peer;
        peer.addTransceiver('video', { direction: 'recvonly' });

        peer.onicecandidate = (event) => {
          if (!isCurrent(connection) || !event.candidate) return;
          connection.candidates.push(event.candidate);
          flushCandidates(connection);
        };
        peer.onconnectionstatechange = () => {
          if (!isCurrent(connection)) return;
          if (peer.connectionState === 'failed' || peer.connectionState === 'closed') {
            scheduleRetry();
          } else if (peer.connectionState === 'disconnected') {
            if (connection.disconnectTimer !== undefined) window.clearTimeout(connection.disconnectTimer);
            connection.disconnectTimer = window.setTimeout(() => {
              if (isCurrent(connection) && peer.connectionState === 'disconnected') scheduleRetry();
            }, DISCONNECT_GRACE_MS);
          } else if (peer.connectionState === 'connected' && connection.disconnectTimer !== undefined) {
            window.clearTimeout(connection.disconnectTimer);
            connection.disconnectTimer = undefined;
          }
        };
        peer.oniceconnectionstatechange = () => {
          if (isCurrent(connection) && peer.iceConnectionState === 'failed') scheduleRetry();
        };
        peer.ontrack = (event) => {
          if (!isCurrent(connection) || event.track.kind !== 'video') return;
          const targetVideo = video;
          if (!targetVideo) return;
          const stream = event.streams[0] ?? new MediaStream([event.track]);
          connection.stream = stream;
          targetVideo.srcObject = stream;
          observeFrames(connection);
          void targetVideo.play().catch(() => undefined);
        };

        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        if (!isCurrent(connection) || !peer.localDescription?.sdp) return;

        const response = await fetch(streamUrl, {
          method: 'POST',
          headers: { Accept: 'application/sdp', 'Content-Type': 'application/sdp' },
          body: peer.localDescription.sdp,
          cache: 'no-store',
          signal: connection.abortController.signal,
        });
        const location = response.headers.get('Location');
        const sessionUrl = location ? new URL(location, streamUrl).toString() : null;
        if (!response.ok) throw new Error(`WHEP ${response.status}`);
        if (!isCurrent(connection)) {
          if (sessionUrl) releaseSession(sessionUrl);
          return;
        }

        connection.sessionUrl = sessionUrl;
        const answer = await response.text();
        if (!answer) throw new Error('WHEP no devolvió una respuesta SDP');
        await peer.setRemoteDescription({ type: 'answer', sdp: answer });
        if (!isCurrent(connection)) return;
        connection.remoteDescriptionAt = Date.now();
        flushCandidates(connection);
      } catch (error) {
        if (isCurrent(connection) && !isAbortError(error)) scheduleRetry();
      }
    }

    const onVideoProgress = () => {
      if (activeConnection) markFrameReceived(activeConnection);
    };
    const onVisibilityChange = () => {
      const connection = activeConnection;
      if (!connection || document.hidden) return;
      if (connection.lastFrameAt && Date.now() - connection.lastFrameAt > FRAME_TIMEOUT_MS) scheduleRetry(true);
    };
    const healthTimer = window.setInterval(() => {
      const connection = activeConnection;
      if (!connection || document.hidden) return;
      const now = Date.now();
      if (!connection.remoteDescriptionAt && now - connection.createdAt > CONNECT_TIMEOUT_MS) {
        scheduleRetry();
      } else if (connection.remoteDescriptionAt && !connection.firstFrameAt && now - connection.remoteDescriptionAt > CONNECT_TIMEOUT_MS) {
        scheduleRetry();
      } else if (connection.lastFrameAt && now - connection.lastFrameAt > FRAME_TIMEOUT_MS) {
        scheduleRetry();
      }
    }, 1_000);

    video.addEventListener('loadeddata', onVideoProgress);
    video.addEventListener('playing', onVideoProgress);
    video.addEventListener('timeupdate', onVideoProgress);
    document.addEventListener('visibilitychange', onVisibilityChange);
    void startConnection();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      window.clearInterval(healthTimer);
      video.removeEventListener('loadeddata', onVideoProgress);
      video.removeEventListener('playing', onVideoProgress);
      video.removeEventListener('timeupdate', onVideoProgress);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      stopConnection();
    };
  }, [enabled, restartKey, streamUrl, videoRef]);

  return { reconnect, state };
}
