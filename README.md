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
- MediaMTX WebRTC: http://localhost:8889

Las cámaras del dashboard se cargan automáticamente desde `mediamtx.yml`. Cada entrada bajo `paths` se expone por la API y su preview WebRTC/WHEP se genera con la ruta pública de MediaMTX. Las credenciales reales de RTSP/FTP deben protegerse y no commitearse en entornos reales.

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
