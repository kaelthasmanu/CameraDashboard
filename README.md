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

El dashboard arranca con cámaras de demostración. Las credenciales reales de RTSP/FTP deben configurarse mediante la API y nunca commitearse.

La segunda fase añade `GET /api/v1/recordings?camera_id=1&day=2026-08-14` y `GET /api/v1/recordings/{id}`. El repositorio actual es demo; el siguiente adaptador debe indexar FTP/SFTP en PostgreSQL y servir archivos mediante Range Requests.

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
