import { FormEvent, useEffect, useState } from 'react';
import { CheckCircle2, UserPlus, UsersRound } from 'lucide-react';
import { api, ApiError } from '../../../shared/lib/api-client';
import type { AuthUser, UserRole } from '../../../shared/types/api';
import { roleLabels } from '../../layout/navigation';

const roleOptions: UserRole[] = ['guardia', 'supervisor', 'admin'];

export function UsersPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('guardia');
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
      const createdUser = await api.createUser({ username, password, role });
      setUsers(current => [...current, createdUser].sort((left, right) => left.username.localeCompare(right.username)));
      setUsername('');
      setPassword('');
      setRole('guardia');
      setSuccess(`Usuario ${createdUser.username} creado correctamente.`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'No se pudo crear el usuario.');
    } finally {
      setSaving(false);
    }
  };

  return <section className="users-page"><div className="users-intro"><div><p className="eyebrow">Acceso y permisos</p><h2>Crear usuario</h2><p className="muted">Asigna el rol adecuado según el nivel de acceso que necesita cada persona.</p></div><span className="admin-only"><UsersRound size={15}/> Solo administradores</span></div><div className="users-layout"><form className="user-form" onSubmit={submit}><label>Usuario<input value={username} onChange={event => setUsername(event.target.value)} minLength={3} maxLength={120} autoComplete="username" required placeholder="nombre.apellido"/></label><label>Contraseña<input value={password} onChange={event => setPassword(event.target.value)} type="password" minLength={8} maxLength={128} autoComplete="new-password" required placeholder="Mínimo 8 caracteres"/></label><label>Rol<select value={role} onChange={event => setRole(event.target.value as UserRole)}>{roleOptions.map(option => <option key={option} value={option}>{roleLabels[option]}</option>)}</select></label><p className="role-help">Guardia: cámaras en vivo. Supervisor: cámaras y grabaciones. Administrador: acceso completo.</p>{error && <div className="form-message error">{error}</div>}{success && <div className="form-message success"><CheckCircle2 size={16}/>{success}</div>}<button className="primary-button" disabled={saving}><UserPlus size={16}/>{saving ? 'Creando usuario…' : 'Crear usuario'}</button></form><section className="user-list-panel"><div className="user-list-heading"><div><p className="eyebrow">Usuarios registrados</p><h3>Accesos actuales</h3></div><span>{users.length}</span></div>{loadingUsers ? <div className="empty">Cargando usuarios…</div> : <div className="users-list">{users.map(user => <div className="user-row" key={user.id}><div className="user-row-avatar">{user.username.slice(0, 2).toUpperCase()}</div><div><b>{user.username}</b><small>{user.is_active ? 'Activo' : 'Inactivo'}</small></div><span className={`role-badge ${user.role}`}>{roleLabels[user.role]}</span></div>)}</div>}</section></div></section>;
}
