import { Activity, Camera, CircleUserRound, Grid2X2, LayoutDashboard, LogOut, Settings, Video } from 'lucide-react';
import type { AuthUser } from '../../../shared/types/api';

export type View = 'overview' | 'live' | 'recordings' | 'activity' | 'settings';

const items: Array<{ id: View; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'overview', label: 'Resumen', icon: LayoutDashboard },
  { id: 'live', label: 'Vista en vivo', icon: Grid2X2 },
  { id: 'recordings', label: 'Grabaciones', icon: Video },
  { id: 'activity', label: 'Actividad', icon: Activity },
];

export function Sidebar({ view, onNavigate, open, user, onLogout }: { view: View; onNavigate: (view: View) => void; open: boolean; user: AuthUser | null; onLogout: () => void }) {
  const username = user?.username ?? 'Cargando…';
  const role = user?.is_admin ? 'Administrador' : 'Operador';
  return <aside className={`sidebar ${open ? 'open' : ''}`}>
    <div className="brand"><span className="brand-mark"><Camera size={18}/></span><span>watchtower</span></div>
    <p className="nav-caption">Operaciones</p>
    <nav>{items.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? 'active' : ''} onClick={() => onNavigate(id)}><Icon size={18}/>{label}</button>)}</nav>
    <div className="side-bottom">
      <button className={view === 'settings' ? 'active' : ''} onClick={() => onNavigate('settings')}><Settings size={18}/> Ajustes</button>
      <div className="user-card">
        <div className="user-avatar"><CircleUserRound size={23}/></div>
        <span><b>{username}</b><small>{role}</small></span>
        <button className="logout-button" onClick={onLogout} title="Cerrar sesión" aria-label="Cerrar sesión"><LogOut size={16}/></button>
      </div>
    </div>
  </aside>;
}
