import { useRef } from 'react';
import { Camera as CameraIcon, MoreVertical, Play, RotateCw, WifiOff } from 'lucide-react';
import { formatDate } from '../../../shared/lib/formatters';
import type { Camera } from '../../../shared/types/api';
import { useWhepStream } from '../hooks/use-whep-stream';

export function CameraCard({ camera, onSelect, streamActive = true }: { camera: Camera; onSelect: (camera: Camera) => void; streamActive?: boolean }) {
  return <article className="camera-card" onClick={() => onSelect(camera)} role="button" tabIndex={0} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') onSelect(camera); }}>
    <div className="feed">
      <div className="feed-top"><span className={`status ${camera.status}`}>{camera.status === 'online' ? 'LIVE' : 'OFFLINE'}</span><span className="cam-id">CAM-{String(camera.id).padStart(2, '0')}</span></div>
      {camera.status === 'online' && camera.enabled ? <CameraStream camera={camera} compact active={streamActive}/> : <div className="offline"><WifiOff size={30}/><span>Cámara desconectada</span><small>{camera.last_seen ? `Última conexión: ${formatDate(camera.last_seen)}` : 'Sin conexión registrada'}</small></div>}
      <button className="expand" aria-label="Abrir cámara" onClick={event => { event.stopPropagation(); onSelect(camera); }}><Play size={14}/></button>
    </div>
    <div className="card-info"><div><h3>{camera.name}</h3><p>{camera.location}</p></div><MoreVertical size={17} className="more"/></div>
  </article>;
}

export function CameraStream({ camera, compact = false, active = true }: { camera: Camera; compact?: boolean; active?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  // El preview es H.264 de bajo bitrate; también se prefiere en el modal para
  // evitar que un stream principal HEVC no compatible con el navegador congele la imagen.
  const streamUrl = camera.preview_url ?? camera.stream_url;
  const enabled = active && camera.status === 'online' && camera.enabled;
  const { reconnect, state } = useWhepStream({ enabled, streamUrl, videoRef });

  const retry = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    reconnect();
  };

  return <div className={`scene ${compact ? 'compact' : ''}`}>
    <video ref={videoRef} className="live-video" autoPlay muted playsInline controls={!compact} onError={reconnect}/>
    {!active && <div className="stream-message paused"><CameraIcon size={30}/><span>Abierta en vista ampliada</span></div>}
    {active && !enabled && <div className="stream-message error"><WifiOff size={30}/><span>Cámara no disponible</span></div>}
    {enabled && state === 'connecting' && <div className="stream-message"><CameraIcon size={34}/><span>Conectando al directo…</span></div>}
    {enabled && state === 'reconnecting' && <div className="stream-message reconnecting"><RotateCw size={30} className="spin"/><span>Reconectando la señal…</span><button className="stream-retry" type="button" onClick={retry}>Reintentar ahora</button></div>}
    {enabled && state === 'unsupported' && <div className="stream-message error"><WifiOff size={30}/><span>Este navegador no admite WebRTC</span><button className="stream-retry" type="button" onClick={retry}>Reintentar</button></div>}
  </div>;
}
