import { useCallback, useEffect, useMemo, useState } from 'react';
import { CircleAlert, Clock3, LogIn, MonitorPlay, RefreshCw, ShieldCheck, UserRoundCheck, UsersRound } from 'lucide-react';
import { ApiError, api } from '../../../shared/lib/api-client';
import { formatPreciseDate } from '../../../shared/lib/formatters';
import type { AdminActivity, UserActivityEvent, UserPresence } from '../../../shared/types/api';
import { roleLabels } from '../../layout/navigation';

function describeEvent(event: UserActivityEvent) {
  if (event.event_type === 'login') return 'inició sesión';
  return event.camera_name ? `abrió la cámara ${event.camera_name}` : 'abrió una cámara';
}

function EventIcon({ eventType }: { eventType: UserActivityEvent['event_type'] }) {
  return eventType === 'camera_opened' ? <MonitorPlay size={17}/> : <LogIn size={17}/>;
}

function PresenceState({ user }: { user: UserPresence }) {
  return <div className="presence-state">
    <span className={`presence-badge ${user.active_now ? 'active' : 'inactive'}`}><i/>{user.active_now ? 'Activo ahora' : 'Inactivo'}</span>
    {!user.is_account_active && <span className="account-disabled">Cuenta desactivada</span>}
    <small>{user.last_seen_at ? `Última señal: ${formatPreciseDate(user.last_seen_at)}` : 'Aún no hay señal de sesión'}</small>
  </div>;
}

export function UserAuditPage({ refreshToken }: { refreshToken: number }) {
  const [audit, setAudit] = useState<AdminActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setAudit(await api.adminActivity());
      setError('');
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'No se pudo cargar la auditoría de usuarios.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 15_000);
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void load();
    };
    document.addEventListener('visibilitychange', refreshWhenVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, [load, refreshToken]);

  const users = useMemo(() => [...(audit?.users ?? [])].sort((left, right) => {
    const activeFirst = Number(right.active_now) - Number(left.active_now);
    return activeFirst || left.username.localeCompare(right.username);
  }), [audit]);
  const activeUsers = users.filter(user => user.active_now).length;
  const activityWindow = audit?.active_window_seconds ?? 45;

  return <section className="audit-page">
    <div className="audit-intro">
      <div><p className="eyebrow">Control de acceso</p><h2>Auditoría de usuarios</h2><p className="muted">Consulta las aperturas de cámaras y el estado de conexión reportado por cada sesión.</p></div>
      <span className="admin-only"><ShieldCheck size={15}/> Solo administradores</span>
    </div>

    <div className="audit-summary">
      <div><span className="audit-summary-icon"><UserRoundCheck size={18}/></span><span><small>Usuarios activos ahora</small><strong>{activeUsers}</strong></span></div>
      <div><span className="audit-summary-icon"><UsersRound size={18}/></span><span><small>Usuarios registrados</small><strong>{users.length}</strong></span></div>
      <div><span className="audit-summary-icon"><Clock3 size={18}/></span><span><small>Ventana de presencia</small><strong>{activityWindow} s</strong></span></div>
    </div>

    {error && <div className="audit-error"><CircleAlert size={17}/><span>{error}</span><button onClick={() => void load()}>Reintentar</button></div>}

    {loading && !audit ? <div className="empty">Cargando actividad de usuarios…</div> : <div className="audit-grid">
      <section className="audit-section presence-section">
        <div className="audit-section-heading"><div><p className="eyebrow">Presencia en tiempo real</p><h3>Estado de los usuarios</h3></div><button className="audit-refresh" onClick={() => void load()} title="Actualizar auditoría" aria-label="Actualizar auditoría"><RefreshCw size={16} className={loading ? 'spin' : ''}/></button></div>
        <p className="audit-explanation">“Activo ahora” significa que una pestaña visible envió una señal al servidor durante los últimos {activityWindow} segundos.</p>
        {!users.length ? <div className="audit-empty">No hay usuarios registrados.</div> : <div className="presence-list">{users.map(user => <div className="presence-row" key={user.id}><div className="presence-avatar">{user.username.slice(0, 2).toUpperCase()}</div><div className="presence-user"><b>{user.username}</b><small>{roleLabels[user.role]}</small></div><PresenceState user={user}/></div>)}</div>}
      </section>

      <section className="audit-section event-section">
        <div className="audit-section-heading"><div><p className="eyebrow">Registro persistente</p><h3>Acciones recientes</h3></div><span className="event-count">{audit?.events.length ?? 0}</span></div>
        {!audit?.events.length ? <div className="audit-empty">Todavía no se han registrado acciones.</div> : <ol className="event-list">{audit.events.map(event => <li key={event.id}><span className={`event-icon ${event.event_type}`}><EventIcon eventType={event.event_type}/></span><div><b>{event.username}</b><p>{describeEvent(event)}</p><small>{roleLabels[event.user_role]} · {formatPreciseDate(event.occurred_at)}</small></div></li>)}</ol>}
      </section>
    </div>}
  </section>;
}
