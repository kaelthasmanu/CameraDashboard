export type CameraStatus = 'online' | 'offline' | 'unknown';
export interface Camera { id: number; name: string; location: string; model: string; stream_url: string; status: CameraStatus; enabled: boolean; last_seen: string | null; }
export interface Recording { id: number; camera_id: number; filename: string; start_time: string; end_time: string; size_bytes: number; duration_seconds: number; }
export interface AuthUser { id: number; username: string; is_active: boolean; is_admin: boolean; }
