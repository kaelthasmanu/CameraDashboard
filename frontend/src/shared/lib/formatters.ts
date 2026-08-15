export const formatDate = (value: string) => new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
export const formatSize = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;
export const formatDuration = (seconds: number) => `${Math.floor(seconds / 60)} min`;
