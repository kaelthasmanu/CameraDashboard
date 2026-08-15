import type { AuthUser, Camera, Recording } from '../types/api';

const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

function authHeaders(headers?: HeadersInit) {
  const result = new Headers(headers);
  const token = localStorage.getItem('access_token');
  if (token) result.set('Authorization', `Bearer ${token}`);
  return result;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: authHeaders(init.headers), credentials: 'include' });
  if (!response.ok) throw new ApiError(response.status, `La API respondió con ${response.status}`);
  return response.json() as Promise<T>;
}

export const api = {
  async login(username: string, password: string) {
    const body = new URLSearchParams({ username, password });
    const result = await request<{ access_token: string }>('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
    localStorage.setItem('access_token', result.access_token);
  },
  me: () => request<AuthUser>('/auth/me'),
  async logout() {
    try { await fetch(`${API_URL}/auth/logout`, { method: 'POST', credentials: 'include' }); }
    finally { localStorage.removeItem('access_token'); }
  },
  cameras: () => request<Camera[]>('/cameras'),
  recordings: (day: string, cameraId?: number) => request<Recording[]>(`/recordings?day=${encodeURIComponent(day)}${cameraId ? `&camera_id=${cameraId}` : ''}`),
  recordingStream: (id: number) => `${API_URL}/recordings/${id}/stream`,
};

export { API_URL };
