import { useEffect, useState } from 'react';
import { CheckCircle2, CircleAlert, LogOut, WifiOff } from 'lucide-react';
import { LoginPage } from './features/auth/components/login-page';
import { useCurrentUser } from './features/auth/hooks/use-current-user';
import { CameraStream } from './features/cameras/components/camera-card';
import { useCameras } from './features/cameras/hooks/use-cameras';
import { PageHeader } from './features/layout/components/page-header';
import { Sidebar } from './features/layout/components/sidebar';
import { canAccessView, canViewRecordings, defaultViewForRole, type View } from './features/layout/navigation';
import { RecordingList } from './features/recordings/components/recording-list';
import { RecordingPlayer } from './features/recordings/components/recording-player';
import { useRecordings } from './features/recordings/hooks/use-recordings';
import { UsersPage } from './features/users/components/users-page';
import { DashboardPage } from './pages/dashboard-page';
import { API_URL, api } from './shared/lib/api-client';
import { formatDate } from './shared/lib/formatters';
import type { Camera, Recording } from './shared/types/api';

const initialDay = new Date().toISOString().slice(0, 10);

export function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem('access_token')));
  const logout = () => { api.logout(); setAuthenticated(false); };
  return authenticated ? <AuthenticatedApp onLogout={logout}/> : <LoginPage onLogin={() => setAuthenticated(true)}/>;
}

function AuthenticatedApp({ onLogout }: { onLogout: () => void }) {
  const [view, setView] = useState<View>('overview');
  const [day, setDay] = useState(initialDay);
  const [query, setQuery] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [playing, setPlaying] = useState<Recording | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const { user, loading: userLoading } = useCurrentUser();
  const cameras = useCameras();
  const recordings = useRecordings(day, canViewRecordings(user?.role));

  useEffect(() => {
    if (!userLoading && !user) onLogout();
  }, [onLogout, user, userLoading]);

  const currentView: View = user && canAccessView(user.role, view)
    ? view
    : user ? defaultViewForRole(user.role) : 'live';

  useEffect(() => {
    if (user && currentView !== view) setView(currentView);
  }, [currentView, user, view]);

  const error = cameras.error || recordings.error;
  const reload = () => { cameras.reload(); recordings.reload(); };
  const navigate = (next: View) => {
    if (user && canAccessView(user.role, next)) setView(next);
    setMobileOpen(false);
  };

  if (userLoading) return <main className="auth-loading"><CircleAlert size={20}/> Verificando tu sesión…</main>;
  if (!user) return null;

  const dashboardProps = {
    cameras: cameras.cameras,
    recordings: recordings.recordings,
    query,
    day,
    loading: cameras.loading,
    onDayChange: setDay,
    onRecordings: () => navigate('recordings'),
    onCameraSelect: setSelectedCamera,
    selectedCameraId: selectedCamera?.id,
    emptyMessage: user.role !== 'admin' && !user.camera_names.length
      ? 'No tienes cámaras asignadas. Contacta a un administrador.'
      : undefined,
  };

  return <div className="app-shell">
    <Sidebar view={currentView} onNavigate={navigate} open={mobileOpen} user={user} onLogout={onLogout}/>
    {mobileOpen && <button className="sidebar-scrim" onClick={() => setMobileOpen(false)} aria-label="Cerrar menú"/>}
    <main className="app-main">
      <PageHeader view={currentView} query={query} onQueryChange={setQuery} onRefresh={reload} onMenu={() => setMobileOpen(value => !value)} user={user}/>
      {error && <div className="alert"><WifiOff size={17}/><span>{error}</span><button onClick={reload}>Reintentar</button></div>}
      {currentView === 'overview' && <DashboardPage {...dashboardProps} showOverview/>}
      {currentView === 'live' && <DashboardPage {...dashboardProps}/>}
      {currentView === 'recordings' && <section className="panel recordings-panel"><div className="toolbar"><div><p className="eyebrow">Archivo de vídeo</p><h2>Grabaciones disponibles</h2><p>Explora y reproduce eventos almacenados de forma segura.</p></div><label className="date"><span>Fecha</span><input type="date" value={day} onChange={event => setDay(event.target.value)}/></label></div>{recordings.loading ? <div className="empty">Cargando grabaciones…</div> : <RecordingList recordings={recordings.recordings} cameras={cameras.cameras} onPlay={setPlaying}/>}</section>}
      {currentView === 'activity' && <ActivityPage cameras={cameras.cameras}/>}
      {currentView === 'users' && <UsersPage cameras={cameras.cameras} camerasLoading={cameras.loading}/>}
      {currentView === 'settings' && <SettingsPage user={user.username} onLogout={onLogout}/>}
    </main>
    {playing && <RecordingPlayer recording={playing} camera={cameras.cameras.find(camera => camera.id === playing.camera_id)} onClose={() => setPlaying(null)}/>} 
    {selectedCamera && <CameraModal camera={selectedCamera} onClose={() => setSelectedCamera(null)}/>} 
  </div>;
}

function ActivityPage({ cameras }: { cameras: Camera[] }) {
  return <section className="panel activity-panel"><p className="eyebrow">Estado de infraestructura</p><h2>Actividad reciente</h2><p className="muted">Última información reportada por cada dispositivo.</p><div className="activity-list">{cameras.map(camera => <div key={camera.id}><span className={`activity-dot ${camera.status}`}/><div><b>{camera.name} · {camera.status === 'online' ? 'En línea' : 'Sin conexión'}</b><small>{camera.last_seen ? `Última señal: ${formatDate(camera.last_seen)}` : 'No hay actividad registrada'}</small></div><span className={`activity-badge ${camera.status}`}>{camera.status}</span></div>)}</div></section>;
}

function SettingsPage({ user, onLogout }: { user: string; onLogout: () => void }) {
  return <section className="panel settings"><p className="eyebrow">Cuenta y conexión</p><h2>Ajustes del sistema</h2><p className="muted">Información de la sesión y de la conexión configurada.</p><div className="settings-grid"><label>Usuario autenticado<input value={user} readOnly/></label><label>URL de la API<input value={API_URL} readOnly/></label></div><div className="saved"><CheckCircle2 size={17}/> Sesión protegida con JWT</div><button className="danger-button" onClick={onLogout}><LogOut size={16}/> Cerrar sesión</button></section>;
}

function CameraModal({ camera, onClose }: { camera: Camera; onClose: () => void }) {
  return <div className="modal-backdrop" onClick={onClose} role="presentation"><section className="camera-modal" onClick={event => event.stopPropagation()} role="dialog" aria-modal="true" aria-label={`Cámara ${camera.name}`}><button className="close" onClick={onClose} aria-label="Cerrar cámara">×</button><CameraStream camera={camera}/><div className="camera-modal-info"><div><p className="eyebrow">Transmisión en vivo</p><h2>{camera.name}</h2><p>{camera.location} · {camera.model}</p></div><span className={`camera-status ${camera.status}`}>{camera.status === 'online' ? 'En línea' : 'Sin conexión'}</span></div></section></div>;
}
