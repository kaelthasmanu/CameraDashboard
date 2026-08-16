import { FormEvent, useEffect, useState } from 'react';
import { Camera as CameraIcon, CheckCircle2, SlidersHorizontal, UserPlus, UsersRound } from 'lucide-react';
import { api, ApiError } from '../../../shared/lib/api-client';
import type { AuthUser, Camera, UserRole } from '../../../shared/types/api';
import { roleLabels } from '../../layout/navigation';

const roleOptions: UserRole[] = ['guardia', 'supervisor', 'admin'];

type CameraAccessSelectorProps = {
  cameras: Camera[];
  camerasLoading: boolean;
  selectedCameraNames: string[];
  onChange: (cameraNames: string[]) => void;
};

function CameraAccessSelector({ cameras, camerasLoading, selectedCameraNames, onChange }: CameraAccessSelectorProps) {
  const selected = new Set(selectedCameraNames);
  const toggle = (cameraName: string) => {
    onChange(selected.has(cameraName)
      ? selectedCameraNames.filter(name => name !== cameraName)
      : [...selectedCameraNames, cameraName]);
  };

  return <fieldset className="camera-access-fieldset"><div className="camera-access-heading"><div><span className="camera-access-title">Cámaras autorizadas</span><small>{selected.size} de {cameras.length} seleccionadas</small></div><div className="camera-access-actions"><button type="button" onClick={() => onChange(cameras.map(camera => camera.name))}>Todas</button><button type="button" onClick={() => onChange([])}>Limpiar</button></div></div>{camerasLoading ? <div className="camera-access-loading">Cargando cámaras…</div> : !cameras.length ? <div className="camera-access-loading">No hay cámaras disponibles.</div> : <div className="camera-access-list">{cameras.map(camera => <label className="camera-access-option" key={camera.name}><input type="checkbox" checked={selected.has(camera.name)} onChange={() => toggle(camera.name)}/><span className="camera-access-icon"><CameraIcon size={15}/></span><span><b>{camera.name}</b><small>{camera.location}</small></span></label>)}</div>}{!selected.size && !camerasLoading && <p className="camera-access-warning">Sin cámaras seleccionadas: este usuario no podrá ver cámaras ni sus grabaciones.</p>}</fieldset>;
}

function CameraAccessModal({ user, cameras, camerasLoading, onClose, onSaved }: { user: AuthUser; cameras: Camera[]; camerasLoading: boolean; onClose: () => void; onSaved: (user: AuthUser) => void }) {
  const [cameraNames, setCameraNames] = useState(user.camera_names);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      onSaved(await api.updateUserCameras(user.id, cameraNames));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'No se pudieron actualizar las cámaras.');
    } finally {
      setSaving(false);
    }
  };

  return <div className="modal-backdrop" onClick={onClose} role="presentation"><section className="camera-access-modal" onClick={event => event.stopPropagation()} role="dialog" aria-modal="true" aria-label={`Cámaras autorizadas para ${user.username}`}><button className="close access-close" onClick={onClose} aria-label="Cerrar">×</button><div className="access-modal-heading"><p className="eyebrow">Permisos de cámara</p><h2>{user.username}</h2><p>{roleLabels[user.role]} · selecciona las cámaras a las que puede acceder.</p></div><CameraAccessSelector cameras={cameras} camerasLoading={camerasLoading} selectedCameraNames={cameraNames} onChange={setCameraNames}/>{error && <div className="form-message error">{error}</div>}<div className="access-modal-actions"><button className="secondary-button" type="button" onClick={onClose}>Cancelar</button><button className="primary-button" type="button" onClick={save} disabled={saving}>{saving ? 'Guardando…' : 'Guardar cámaras'}</button></div></section></div>;
}

export function UsersPage({ cameras, camerasLoading }: { cameras: Camera[]; camerasLoading: boolean }) {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('guardia');
  const [cameraNames, setCameraNames] = useState<string[]>([]);
  const [editingUser, setEditingUser] = useState<AuthUser | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    api.users()
      .then(setUsers)
      .catch(() => setError('No se pudieron cargar los usuarios.'))
      .finally(() => setLoadingUsers(false));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const createdUser = await api.createUser({
        username,
        password,
        role,
        camera_names: role === 'admin' ? [] : cameraNames,
      });
      setUsers(current => [...current, createdUser].sort((left, right) => left.username.localeCompare(right.username)));
      setUsername('');
      setPassword('');
      setRole('guardia');
      setCameraNames([]);
      setSuccess(`Usuario ${createdUser.username} creado correctamente.`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'No se pudo crear el usuario.');
    } finally {
      setSaving(false);
    }
  };

  const saveUserCameras = (updatedUser: AuthUser) => {
    setUsers(current => current.map(user => user.id === updatedUser.id ? updatedUser : user));
    setEditingUser(null);
  };

  return <section className="users-page"><div className="users-intro"><div><p className="eyebrow">Acceso y permisos</p><h2>Crear usuario</h2><p className="muted">Asigna un rol y las cámaras que podrá consultar cada persona.</p></div><span className="admin-only"><UsersRound size={15}/> Solo administradores</span></div><div className="users-layout"><form className="user-form" onSubmit={submit}><label>Usuario<input value={username} onChange={event => setUsername(event.target.value)} minLength={3} maxLength={120} autoComplete="username" required placeholder="nombre.apellido"/></label><label>Contraseña<input value={password} onChange={event => setPassword(event.target.value)} type="password" minLength={8} maxLength={128} autoComplete="new-password" required placeholder="Mínimo 8 caracteres"/></label><label>Rol<select value={role} onChange={event => setRole(event.target.value as UserRole)}>{roleOptions.map(option => <option key={option} value={option}>{roleLabels[option]}</option>)}</select></label>{role === 'admin' ? <p className="role-help">Los administradores tienen acceso automático a todas las cámaras del sistema.</p> : <CameraAccessSelector cameras={cameras} camerasLoading={camerasLoading} selectedCameraNames={cameraNames} onChange={setCameraNames}/>}<p className="role-help">Guardia: cámaras en vivo. Supervisor: cámaras y grabaciones. Administrador: acceso completo.</p>{error && <div className="form-message error">{error}</div>}{success && <div className="form-message success"><CheckCircle2 size={16}/>{success}</div>}<button className="primary-button" disabled={saving}><UserPlus size={16}/>{saving ? 'Creando usuario…' : 'Crear usuario'}</button></form><section className="user-list-panel"><div className="user-list-heading"><div><p className="eyebrow">Usuarios registrados</p><h3>Accesos actuales</h3></div><span>{users.length}</span></div>{loadingUsers ? <div className="empty">Cargando usuarios…</div> : <div className="users-list">{users.map(user => <div className="user-row" key={user.id}><div className="user-row-avatar">{user.username.slice(0, 2).toUpperCase()}</div><div><b>{user.username}</b><small>{user.role === 'admin' ? 'Todas las cámaras' : user.camera_names.length ? `${user.camera_names.length} cámara${user.camera_names.length === 1 ? '' : 's'} asignada${user.camera_names.length === 1 ? '' : 's'}` : 'Sin cámaras asignadas'}</small></div><span className={`role-badge ${user.role}`}>{roleLabels[user.role]}</span>{user.role !== 'admin' && <button className="manage-cameras-button" type="button" onClick={() => setEditingUser(user)}><SlidersHorizontal size={14}/> Gestionar</button>}</div>)}</div>}</section></div>{editingUser && <CameraAccessModal key={editingUser.id} user={editingUser} cameras={cameras} camerasLoading={camerasLoading} onClose={() => setEditingUser(null)} onSaved={saveUserCameras}/>}</section>;
}
