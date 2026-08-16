import type { UserRole } from '../../shared/types/api';

export type View = 'overview' | 'live' | 'recordings' | 'activity' | 'settings' | 'users';

const roleViews: Record<UserRole, readonly View[]> = {
  admin: ['overview', 'live', 'recordings', 'activity', 'settings', 'users'],
  supervisor: ['live', 'recordings'],
  guardia: ['live'],
};

export const roleLabels: Record<UserRole, string> = {
  admin: 'Administrador',
  supervisor: 'Supervisor',
  guardia: 'Guardia',
};

export function canAccessView(role: UserRole | undefined, view: View) {
  return role ? roleViews[role].includes(view) : false;
}

export function defaultViewForRole(role: UserRole): View {
  return role === 'admin' ? 'overview' : 'live';
}

export function canViewRecordings(role: UserRole | undefined) {
  return role === 'admin' || role === 'supervisor';
}
