import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../shared/lib/api-client';
import type { Recording } from '../../../shared/types/api';
export function useRecordings(day: string) { const [data, setData] = useState<Recording[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const reload = useCallback(async () => { setLoading(true); setError(''); try { setData(await api.recordings(day)); } catch (e) { setError(e instanceof Error ? e.message : 'No se pudieron cargar las grabaciones'); } finally { setLoading(false); } }, [day]); useEffect(() => { reload(); }, [reload]); return { recordings: data, loading, error, reload }; }
