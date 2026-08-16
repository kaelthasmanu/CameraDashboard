import { Menu, RefreshCw, Search } from 'lucide-react';
import type { AuthUser } from '../../../shared/types/api';
import type { View } from '../navigation';

const titles: Record<View, { title: string; crumb: string }> = {
  overview: { title: 'Centro de control', crumb: 'Resumen' },
  live: { title: 'Vista en vivo', crumb: 'Monitoreo' },
  recordings: { title: 'Grabaciones', crumb: 'Archivo' },
  activity: { title: 'Actividad del sistema', crumb: 'Operaciones' },
  settings: { title: 'Ajustes', crumb: 'Cuenta y sistema' },
  users: { title: 'Usuarios', crumb: 'Administración' },
};

export function PageHeader({ view, query, onQueryChange, onRefresh, onMenu, user }: { view: View; query: string; onQueryChange: (value: string) => void; onRefresh: () => void; onMenu: () => void; user: AuthUser | null }) {
  const initials = (user?.username ?? 'WT').slice(0, 2).toUpperCase();
  const canSearchCameras = view === 'overview' || view === 'live';
  return <header className="page-header"><button className="mobile menu-button" onClick={onMenu} aria-label="Abrir menú"><Menu/></button><div><p className="eyebrow">Operaciones · {titles[view].crumb}</p><h1>{titles[view].title}</h1></div><div className="header-actions">{canSearchCameras && <label className="search"><Search size={17}/><input value={query} onChange={event => onQueryChange(event.target.value)} placeholder="Buscar cámaras…" aria-label="Buscar cámaras"/></label>}<button className="icon-btn" onClick={onRefresh} aria-label="Actualizar datos" title="Actualizar"><RefreshCw size={18}/></button><div className="avatar" title={user?.username}>{initials}</div></div></header>;
}
