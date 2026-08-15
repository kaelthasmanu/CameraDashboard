import type { Camera, Recording } from '../types/api';
const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '');
async function request<T>(path: string, init?: RequestInit): Promise<T> { const response = await fetch(`${API_URL}${path}`, init); if (!response.ok) throw new Error(`La API respondió con ${response.status}`); return response.json() as Promise<T>; }
export const api = { cameras: () => request<Camera[]>('/cameras'), recordings: (day: string, cameraId?: number) => request<Recording[]>(`/recordings?day=${encodeURIComponent(day)}${cameraId ? `&camera_id=${cameraId}` : ''}`), recordingStream: (id: number) => `${API_URL}/recordings/${id}/stream` };
export { API_URL };
