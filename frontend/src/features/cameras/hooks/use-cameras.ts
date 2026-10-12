import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../shared/lib/api-client';
import type { Camera } from '../../../shared/types/api';
export function useCameras() {
	const [data, setData] = useState<Camera[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState('');
	const reload = useCallback(async (showLoading = true) => {
		if (showLoading) setLoading(true);
		setError('');
		try {
			setData(await api.cameras());
		} catch (e) {
			setError(e instanceof Error ? e.message : 'No se pudieron cargar las cámaras');
		} finally {
			if (showLoading) setLoading(false);
		}
	}, []);

	useEffect(() => {
		void reload();
		const interval = window.setInterval(() => void reload(false), 10000);
		return () => window.clearInterval(interval);
	}, [reload]);

	return { cameras: data, loading, error, reload };
}
