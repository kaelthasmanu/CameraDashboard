import { ListFilter, Play, RotateCcw, Search, Video, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { formatDate, formatDuration, formatSize } from '../../../shared/lib/formatters';
import type { Camera, Recording } from '../../../shared/types/api';

type SortOption = 'date-desc' | 'date-asc' | 'name-asc' | 'name-desc' | 'camera-asc' | 'size-desc' | 'size-asc' | 'duration-desc' | 'duration-asc';

const megabyte = 1024 * 1024;

export function RecordingList({ recordings, cameras, onPlay }: { recordings: Recording[]; cameras: Camera[]; onPlay: (recording: Recording) => void }) {
	const [search, setSearch] = useState('');
	const [cameraId, setCameraId] = useState('all');
	const [sizeFilter, setSizeFilter] = useState('all');
	const [durationFilter, setDurationFilter] = useState('all');
	const [minSize, setMinSize] = useState('');
	const [maxSize, setMaxSize] = useState('');
	const [minDuration, setMinDuration] = useState('');
	const [maxDuration, setMaxDuration] = useState('');
	const [sort, setSort] = useState<SortOption>('date-desc');

	const cameraName = (recording: Recording) => cameras.find(camera => camera.id === recording.camera_id)?.name ?? `Cámara ${recording.camera_id}`;
	const hasFilters = search || cameraId !== 'all' || sizeFilter !== 'all' || durationFilter !== 'all' || minSize || maxSize || minDuration || maxDuration || sort !== 'date-desc';

	const clearFilters = () => {
		setSearch(''); setCameraId('all'); setSizeFilter('all'); setDurationFilter('all');
		setMinSize(''); setMaxSize(''); setMinDuration(''); setMaxDuration(''); setSort('date-desc');
	};

	const visibleRecordings = useMemo(() => {
		const normalizedSearch = search.trim().toLocaleLowerCase();
		const filtered = recordings.filter(recording => {
			const name = recording.filename.toLocaleLowerCase();
			const camera = cameraName(recording).toLocaleLowerCase();
			const size = recording.size_bytes / megabyte;
			const duration = recording.duration_seconds / 60;
			const matchesSizePreset = sizeFilter === 'all' || (sizeFilter === 'under-50' && size < 50) || (sizeFilter === '50-100' && size >= 50 && size <= 100) || (sizeFilter === 'over-100' && size > 100);
			const matchesDurationPreset = durationFilter === 'all' || (durationFilter === 'under-5' && duration < 5) || (durationFilter === '5-30' && duration >= 5 && duration <= 30) || (durationFilter === 'over-30' && duration > 30);
			return (!normalizedSearch || name.includes(normalizedSearch) || camera.includes(normalizedSearch))
				&& (cameraId === 'all' || recording.camera_id === Number(cameraId))
				&& matchesSizePreset && (!minSize || size >= Number(minSize)) && (!maxSize || size <= Number(maxSize))
				&& matchesDurationPreset && (!minDuration || duration >= Number(minDuration)) && (!maxDuration || duration <= Number(maxDuration));
		});

		return filtered.sort((left, right) => {
			if (sort === 'name-asc' || sort === 'name-desc') return left.filename.localeCompare(right.filename, 'es') * (sort === 'name-asc' ? 1 : -1);
			if (sort === 'camera-asc') return cameraName(left).localeCompare(cameraName(right), 'es');
			if (sort === 'size-asc' || sort === 'size-desc') return (left.size_bytes - right.size_bytes) * (sort === 'size-asc' ? 1 : -1);
			if (sort === 'duration-asc' || sort === 'duration-desc') return (left.duration_seconds - right.duration_seconds) * (sort === 'duration-asc' ? 1 : -1);
			return (new Date(left.start_time).getTime() - new Date(right.start_time).getTime()) * (sort === 'date-asc' ? 1 : -1);
		});
	}, [recordings, cameras, search, cameraId, sizeFilter, durationFilter, minSize, maxSize, minDuration, maxDuration, sort]);

	return <div className="recordings-browser">
		<div className="recording-filters">
			<div className="recording-filter-head"><div><span className="label">Organizar archivo</span><strong>{visibleRecordings.length} de {recordings.length} grabaciones</strong></div>{hasFilters && <button className="clear-filters" onClick={clearFilters}><RotateCcw size={13}/> Limpiar filtros</button>}</div>
			<div className="filter-grid">
				<label className="filter-field filter-search"><span>Buscar por nombre o cámara</span><div className="filter-input"><Search size={15}/><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Ej. entrada, pasillo..."/><button type="button" onClick={() => setSearch('')} aria-label="Borrar búsqueda">{search && <X size={14}/>}</button></div></label>
				<label className="filter-field"><span>Cámara</span><select value={cameraId} onChange={event => setCameraId(event.target.value)}><option value="all">Todas las cámaras</option>{cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select></label>
				<label className="filter-field"><span>Ordenar por</span><select value={sort} onChange={event => setSort(event.target.value as SortOption)}><option value="date-desc">Más recientes primero</option><option value="date-asc">Más antiguas primero</option><option value="name-asc">Nombre A-Z</option><option value="name-desc">Nombre Z-A</option><option value="camera-asc">Cámara A-Z</option><option value="size-desc">Tamaño mayor primero</option><option value="size-asc">Tamaño menor primero</option><option value="duration-desc">Duración mayor primero</option><option value="duration-asc">Duración menor primero</option></select></label>
				<label className="filter-field"><span>Tamaño</span><select value={sizeFilter} onChange={event => setSizeFilter(event.target.value)}><option value="all">Cualquier tamaño</option><option value="under-50">Menores de 50 MB</option><option value="50-100">Entre 50 y 100 MB</option><option value="over-100">Mayores de 100 MB</option></select></label>
				<label className="filter-field"><span>Duración</span><select value={durationFilter} onChange={event => setDurationFilter(event.target.value)}><option value="all">Cualquier duración</option><option value="under-5">Menos de 5 min</option><option value="5-30">Entre 5 y 30 min</option><option value="over-30">Más de 30 min</option></select></label>
			</div>
			<div className="custom-filters"><span className="filter-caption"><ListFilter size={14}/> Rangos personalizados</span><label><span>Tamaño mínimo (MB)</span><input type="number" min="0" value={minSize} onChange={event => setMinSize(event.target.value)} placeholder="0"/></label><label><span>Tamaño máximo (MB)</span><input type="number" min="0" value={maxSize} onChange={event => setMaxSize(event.target.value)} placeholder="Sin límite"/></label><label><span>Duración mínima (min)</span><input type="number" min="0" value={minDuration} onChange={event => setMinDuration(event.target.value)} placeholder="0"/></label><label><span>Duración máxima (min)</span><input type="number" min="0" value={maxDuration} onChange={event => setMaxDuration(event.target.value)} placeholder="Sin límite"/></label></div>
		</div>
		{!recordings.length ? <div className="empty">No hay grabaciones para este día.</div> : !visibleRecordings.length ? <div className="empty">Ninguna grabación coincide con estos filtros.</div> : <div className="recording-list">{visibleRecordings.map(recording => <div className="recording-row" key={recording.id}><span className="recording-icon"><Video size={16}/></span><div><b>{recording.filename}</b><small>{cameraName(recording)} · {formatDate(recording.start_time)}</small></div><span className="meta">{formatDuration(recording.duration_seconds)} · {formatSize(recording.size_bytes)}</span><button className="play" onClick={() => onPlay(recording)}><Play size={15}/> Reproducir</button></div>)}</div>}
	</div>;
}
