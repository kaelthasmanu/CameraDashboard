import { X } from 'lucide-react';
import { api } from '../../../shared/lib/api-client';
import { formatDate, formatSize } from '../../../shared/lib/formatters';
import type { Camera, Recording } from '../../../shared/types/api';
export function RecordingPlayer({ recording, camera, onClose }: { recording: Recording; camera?: Camera; onClose: () => void }) { return <div className="modal-backdrop" onClick={onClose}><div className="player" onClick={event => event.stopPropagation()}><button className="close" onClick={onClose} aria-label="Cerrar"><X/></button><video className="video-player" controls autoPlay src={api.recordingStream(recording.id)}><track kind="captions"/></video><h2>{camera?.name ?? recording.filename}</h2><p>{formatDate(recording.start_time)} · {formatSize(recording.size_bytes)}</p></div></div>; }
