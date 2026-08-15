# Hikvision Camera Dashboard

Dashboard multi-cámara con React + TypeScript en el frontend y FastAPI en el backend. La estructura sigue Clean Architecture: dominio independiente, casos de uso, puertos y adaptadores.

## Inicio rápido

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- MediaMTX HLS: http://localhost:8888
- MediaMTX WebRTC/WHEP: http://localhost:8889

Las cámaras del dashboard se cargan automáticamente desde `mediamtx.yml`. MediaMTX entrega vídeo por WebRTC/WHEP (no por WebSocket), que es el transporte de baja latencia adecuado para vídeo en navegador. Cada cámara puede tener dos paths: `nombre` para el stream principal y `nombre_preview` para el substream H.264 de menor bitrate. La API devuelve `stream_url` y, cuando existe el par, `preview_url`; tanto la cuadrícula como el modal prefieren el preview compatible con navegador y usan el principal sólo como fallback.

Parte de una configuración segura con `cp mediamtx.example.yml mediamtx.yml` y sustituye los placeholders. Mantén el archivo real privado y usa el template para compartir configuración sin credenciales RTSP.

MediaMTX usa el puerto 8189 para el tráfico WebRTC, además de 8889 para la señalización. Docker publica 8189 por UDP (preferido) y TCP (fallback). Por defecto se anuncia `localhost`, para usarlo desde la misma máquina. Para abrir el dashboard desde otro equipo, configura ambas URLs públicas en `.env` antes de arrancar:

```bash
MEDIAMTX_WEBRTC_PUBLIC_URL=http://IP_O_DNS_DEL_SERVIDOR:8889
MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS=IP_O_DNS_DEL_SERVIDOR
```

Se pueden indicar varios valores separados por comas. Para un stream fluido, usa el substream H.264 (`h264Preview_01_sub`) y el transporte RTSP por TCP; H.265 y RTP/UDP de entrada suelen causar incompatibilidades de navegador o pérdida de fotogramas. En cada cámara configura H.264 Baseline, sin B-frames y con un GOP/intervalo de keyframes corto (aprox. 1–2 segundos): H.264 por sí solo no garantiza que WebRTC del navegador pueda decodificarlo correctamente.

Después de agregar o cambiar cámaras en `mediamtx.yml`, recrea el backend para que vuelva a leer la configuración:

```bash
docker compose up -d --build backend
```

Para un servidor FTP anónimo usa `STORAGE_BACKEND=ftp`, `FTP_ANONYMOUS=true`, `FTP_USER=anonymous` y un correo como `FTP_PASSWORD`. `FTP_ROOT` permite indicar el directorio raíz remoto.

Las grabaciones FTP se indexan desde `FTP_ROOT/YYYY/MM/DD/*.mp4`; se reconocen nombres como `RLC-810A_00_20260814150544.mp4` y se sirven mediante Range Requests.

La persistencia se migra con `cd backend && alembic upgrade head`. El endpoint `GET /api/v1/recordings/{id}/stream` acepta `Range: bytes=...` y soporta almacenamiento local, FTP o SFTP mediante `STORAGE_BACKEND=local|ftp|sftp`.

## Estructura

```text
backend/app/
  domain/          Entidades y contratos del negocio
  application/     Casos de uso
  infrastructure/  Configuración y adaptadores externos
  presentation/    API HTTP
frontend/src/
  features/        Cámaras, grabaciones y estado de aplicación
  shared/          Componentes y cliente HTTP reutilizable
```

## Calidad

```bash
cd backend && pip install -r requirements.txt && pytest
cd frontend && npm install && npm run lint && npm run build
```

Para producción, conectar un MediaMTX real para WebRTC, un scanner FTP/SFTP periódico, autenticación JWT/Argon2, migraciones Alembic y HTTPS.
