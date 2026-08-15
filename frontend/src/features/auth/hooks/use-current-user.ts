import { useEffect, useState } from 'react';
import { api } from '../../../shared/lib/api-client';
import type { AuthUser } from '../../../shared/types/api';
export function useCurrentUser() { const [user, setUser] = useState<AuthUser | null>(null); const [loading, setLoading] = useState(true); useEffect(() => { api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)); }, []); return { user, loading }; }
