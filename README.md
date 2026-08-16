# Hikvision Camera Dashboard

Multi-camera dashboard with React + TypeScript on the frontend and FastAPI on the backend. The structure follows Clean Architecture: independent domain, use cases, ports, and adapters.

## Quick start

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- MediaMTX HLS: http://localhost:8888
- MediaMTX WebRTC/WHEP: http://localhost:8889

Dashboard cameras are loaded automatically from `mediamtx.yml`. MediaMTX delivers video over WebRTC/WHEP (not WebSocket), which is the appropriate low-latency transport for browser video. Each camera can have two paths: `name` for the main stream and `name_preview` for the lower-bitrate H.264 substream. The API returns `stream_url` and, when the pair exists, `preview_url`; both the grid and the modal prefer the browser-compatible preview and use the main stream only as a fallback.

Start with a secure configuration using `cp mediamtx.example.yml mediamtx.yml` and replace the placeholders. Keep the real file private and use the template to share configuration without RTSP credentials.

MediaMTX uses port 8189 for WebRTC traffic, in addition to 8889 for signaling. Docker exposes 8189 over UDP (preferred) and TCP (fallback). By default, it advertises `localhost` for use on the same machine. To open the dashboard from another device, configure both public URLs in `.env` before starting:

```bash
MEDIAMTX_WEBRTC_PUBLIC_URL=http://SERVER_IP_OR_DNS:8889
MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS=SERVER_IP_OR_DNS
```

Multiple comma-separated values can be specified. For smooth streaming, use the H.264 substream (`h264Preview_01_sub`) and RTSP over TCP; H.265 and incoming RTP/UDP often cause browser incompatibilities or dropped frames. Configure each camera with H.264 Baseline, no B-frames, and a short GOP/keyframe interval (about 1–2 seconds): H.264 alone does not guarantee that browser WebRTC can decode it correctly.

After adding or changing cameras in `mediamtx.yml`, recreate the backend so it rereads the configuration:

```bash
docker compose up -d --build backend
```

For an anonymous FTP server, use `STORAGE_BACKEND=ftp`, `FTP_ANONYMOUS=true`, `FTP_USER=anonymous`, and an email address as `FTP_PASSWORD`. `FTP_ROOT` lets you specify the remote root directory.

FTP recordings are indexed from `FTP_ROOT/YYYY/MM/DD/`. The filename must end with a 14-digit timestamp (`YYYYMMDDhhmmss`), for example `NodoRedes_00_20260815100739.mp4`, `PasilloRedes_00_20260815093551.mp4`, or the historical name `RLC-810A_00_20260815053452.mp4`. The prefix can contain hyphens and underscores; the system uses the last 14 digits before the extension as the date.

Associate each FTP prefix with the dashboard camera through `FTP_CAMERA_PREFIXES`, using comma-separated pairs in the `prefix:camera_id` format. Multiple aliases can be declared for the same camera, so a rename does not disconnect historical recordings:

```bash
# Current IDs, based on the order of the main paths in mediamtx.yml.
# The parser ignores the channel suffix (_00, _01, etc.).
FTP_CAMERA_PREFIXES=NodoRedes:1,PasilloRedes:2,RLC-810A:1
```

| ID | MediaMTX path | Known prefixes |
| --- | --- | --- |
| 1 | `redes` | `NodoRedes_00`, `RLC-810A_00` (legacy) |
| 2 | `pasillo_redes` | `PasilloRedes_00` |

If another real camera name appears, add another pair, for example `PuertaTercerPiso:4`, and recreate the backend. Do not blindly assign a generic model prefix to multiple cameras: it can only be associated with certainty when that name identifies a specific camera. The `.txt` files accompanying videos are treated as metadata and are not shown as playable recordings.

Run persistence migrations with `cd backend && alembic upgrade head`; with Docker, use `docker compose run --rm backend alembic upgrade head`. Before starting an existing installation after this update, apply the migration: it assigns existing administrators the `Admin` role and existing non-administrators the `Supervisor` role; users created afterward are assigned explicitly. The `GET /api/v1/recordings/{id}/stream` endpoint accepts `Range: bytes=...` and supports local, FTP, or SFTP storage through `STORAGE_BACKEND=local|ftp|sftp`.

## Roles and camera access

- **Admin** can access every camera and manage users.
- **Supervisor** can access live views and recordings only for cameras assigned by an admin.
- **Guardia** can access live views only for cameras assigned by an admin.

Camera assignments use the stable MediaMTX path name, rather than its dashboard ID, so reordering paths does not change a user's permissions. The access table starts empty after the migration: existing non-admin users must be assigned cameras by an administrator before they can view any. These permissions protect the dashboard API; deployments that expose MediaMTX directly should also add MediaMTX authentication or an authorization-aware proxy for network-level stream protection.

## User audit and presence

Only an **Admin** can open **Auditoría** in the web application. It shows successful logins and intentional camera openings, together with each account's latest server-observed session signal. A user is displayed as active only when at least one visible browser tab has sent a heartbeat during the previous 45 seconds; the UI also shows the exact server timestamp of the last signal. Hidden tabs immediately report themselves as inactive, and an unexpected browser or network loss naturally expires after the same window.

Audit timestamps are generated by the API in UTC, not by the browser. The activity record represents actions made through this dashboard; because WHEP streams are currently reachable directly through MediaMTX, protecting MediaMTX with authentication or an authorization-aware proxy is still required if every network-level stream access must be auditable.

## Structure

```text
backend/app/
  domain/          Business entities and contracts
  application/     Use cases
  infrastructure/  Configuration and external adapters
  presentation/    HTTP API
frontend/src/
  features/        Cameras, recordings, and application state
  shared/          Reusable components and HTTP client
```

## Quality

```bash
cd backend && pip install -r requirements.txt && pytest
cd frontend && npm install && npm run lint && npm run build
```

For production, connect a real MediaMTX instance for WebRTC, a periodic FTP/SFTP scanner, JWT/Argon2 authentication, Alembic migrations, and HTTPS.
