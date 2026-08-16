export type CameraStatus = 'online' | 'offline' | 'unknown';
export type UserRole = 'admin' | 'supervisor' | 'guardia';
export interface Camera { id: number; name: string; location: string; model: string; stream_url: string; preview_url?: string | null; status: CameraStatus; enabled: boolean; last_seen: string | null; }
export interface Recording { id: number; camera_id: number; filename: string; start_time: string; end_time: string; size_bytes: number; duration_seconds: number; }
export interface AuthUser { id: number; username: string; is_active: boolean; is_admin: boolean; role: UserRole; camera_names: string[]; }
export interface CreateUserInput { username: string; password: string; role: UserRole; camera_names: string[]; }
export type UserActivityType = 'login' | 'camera_opened';
export interface UserActivityEvent {
  id: number;
  user_id: number;
  username: string;
  user_role: UserRole;
  event_type: UserActivityType;
  camera_name: string | null;
  occurred_at: string;
}
export interface UserPresence {
  id: number;
  username: string;
  role: UserRole;
  is_account_active: boolean;
  active_now: boolean;
  last_seen_at: string | null;
}
export interface AdminActivity {
  events: UserActivityEvent[];
  users: UserPresence[];
  active_window_seconds: number;
}
