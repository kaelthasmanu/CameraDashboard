import { useState } from 'react';
import { AlertCircle, LoaderCircle, X } from 'lucide-react';
import { api } from '../../../shared/lib/api-client';
import { formatDate, formatSize } from '../../../shared/lib/formatters';
import type { Camera, Recording } from '../../../shared/types/api';

export function RecordingPlayer({ recording, camera, onClose }: { recording: Recording; camera?: Camera; onClose: () => void }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  return <div className="modal-backdrop" onClick={onClose} role="presentation">
    <section className="player" onClick={event => event.stopPropagation()} aria-modal="true" role="dialog" aria-label={`Grabación ${recording.filename}`}>
      <button className="close" onClick={onClose} aria-label="Cerrar reproductor"><X size={18}/></button>
      <div className="player-stage">
        {loading && !error && <div className="player-state"><LoaderCircle className="spin" size={28}/><span>Preparando reproducción…</span></div>}
        {error && <div className="player-state player-error"><AlertCircle size={28}/><span>No fue posible reproducir esta grabación. Verifica la conexión con FTP.</span></div>}
        <video className={`video-player ${loading || error ? 'hidden-video' : ''}`} controls autoPlay crossOrigin="use-credentials" src={api.recordingStream(recording.id)} onCanPlay={() => setLoading(false)} onError={() => { setLoading(false); setError(true); }}/>
      </div>
      <div className="player-details"><div><p className="eyebrow">Grabación archivada</p><h2>{camera?.name ?? recording.filename}</h2><p>{formatDate(recording.start_time)} · {formatSize(recording.size_bytes)}</p></div><span className="recording-duration">{Math.ceil(recording.duration_seconds / 60)} min</span></div>
    </section>
  </div>;
}
