import { useEffect, useState } from 'react';
import { api } from '../../../shared/lib/api-client';
import type { AlarmPreferences } from '../../../shared/types/api';

export function useAlarmPreferences(userId: number | undefined) {
  const [preferences, setPreferences] = useState<AlarmPreferences>({});

  useEffect(() => {
    if (userId === undefined) return;
    setPreferences({});
    api.alarmPreferences().then(setPreferences).catch(() => setPreferences({}));
  }, [userId]);

  const updatePreference = async (cameraId: number, cameraName: string, enabled: boolean) => {
    const previous = preferences[cameraName] ?? true;
    setPreferences(current => ({ ...current, [cameraName]: enabled }));
    try {
      const updated = await api.updateAlarmPreference(cameraId, enabled);
      setPreferences(current => ({ ...current, ...updated }));
    } catch (error) {
      setPreferences(current => ({ ...current, [cameraName]: previous }));
      throw error;
    }
  };

  return { preferences, updatePreference };
}