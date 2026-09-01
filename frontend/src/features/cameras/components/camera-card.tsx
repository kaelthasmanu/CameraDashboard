import { useRef } from 'react';
import { Bell, BellOff, BellRing, Camera as CameraIcon, MoreVertical, Play, RotateCw, WifiOff } from 'lucide-react';
import { formatDate } from '../../../shared/lib/formatters';
import type { Camera } from '../../../shared/types/api';
import { useMotionAlarm } from '../hooks/use-motion-alarm';
import { useWhepStream } from '../hooks/use-whep-stream';

export function CameraCard({ camera, onSelect, streamActive = true, alarmEnabled = true, personDetected = false, onAlarmToggle }: { camera: Camera; onSelect: (camera: Camera) => void; streamActive?: boolean; alarmEnabled?: boolean; personDetected?: boolean; onAlarmToggle?: (enabled: boolean) => void }) {
  return <article className="camera-card" onClick={() => onSelect(camera)} role="button" tabIndex={0} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') onSelect(camera); }}>
    <div className="feed">
      <div className="feed-top"><span className={`status ${camera.status}`}>{camera.status === 'online' ? 'LIVE' : 'OFFLINE'}</span><span className="cam-id">CAM-{String(camera.id).padStart(2, '0')}</span></div>
      {camera.status === 'online' && camera.enabled ? <CameraStream camera={camera} compact active={streamActive} alarmEnabled={alarmEnabled} personDetected={personDetected}/> : <div className="offline"><WifiOff size={30}/><span>Cámara desconectada</span><small>{camera.last_seen ? `Última conexión: ${formatDate(camera.last_seen)}` : 'Sin conexión registrada'}</small></div>}
      <button className="alarm-toggle" type="button" aria-label={alarmEnabled ? 'Desactivar alarma' : 'Activar alarma'} onClick={event => { event.stopPropagation(); onAlarmToggle?.(!alarmEnabled); }}>{alarmEnabled ? <Bell size={15}/> : <BellOff size={15}/>}</button><button className="expand" aria-label="Abrir cámara" onClick={event => { event.stopPropagation(); onSelect(camera); }}><Play size={14}/></button>
    </div>
    <div className="card-info"><div><h3>{camera.name}</h3><p>{camera.location}</p></div><MoreVertical size={17} className="more"/></div>
  </article>;
}

export function CameraStream({ camera, compact = false, active = true, alarmEnabled = true, personDetected = false }: { camera: Camera; compact?: boolean; active?: boolean; alarmEnabled?: boolean; personDetected?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  // The preview is low-bitrate H.264; it is also preferred in the modal to
  // prevent an unsupported HEVC main stream from freezing the image in the browser.
  const streamUrl = camera.preview_url ?? camera.stream_url;
  const enabled = active && camera.status === 'online' && camera.enabled;
  const { reconnect, state } = useWhepStream({ enabled, streamUrl, videoRef });
  const motionDetected = useMotionAlarm(videoRef, alarmEnabled && enabled, personDetected);

  const retry = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    reconnect();
  };

  return <div className={`scene ${compact ? 'compact' : ''} ${motionDetected ? 'motion-detected' : ''}`}>
    <video ref={videoRef} className="live-video" autoPlay muted playsInline controls={!compact} onError={reconnect}/>
    {motionDetected && <div className="motion-alert" role="status"><BellRing size={14} className="alarm-ring"/>{personDetected ? 'Persona detectada' : 'Movimiento detectado'}</div>}
    {!active && <div className="stream-message paused"><CameraIcon size={30}/><span>Abierta en vista ampliada</span></div>}
    {active && !enabled && <div className="stream-message error"><WifiOff size={30}/><span>Cámara no disponible</span></div>}
    {enabled && state === 'connecting' && <div className="stream-message"><CameraIcon size={34}/><span>Conectando al directo…</span></div>}
    {enabled && state === 'reconnecting' && <div className="stream-message reconnecting"><RotateCw size={30} className="spin"/><span>Reconectando la señal…</span><button className="stream-retry" type="button" onClick={retry}>Reintentar ahora</button></div>}
    {enabled && state === 'unsupported' && <div className="stream-message error"><WifiOff size={30}/><span>Este navegador no admite WebRTC</span><button className="stream-retry" type="button" onClick={retry}>Reintentar</button></div>}
  </div>;
}
