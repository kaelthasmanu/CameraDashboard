# Guia de desarrollo local

Esta guia es una alternativa al arranque completo con `docker compose up --build`: ejecuta React/Vite y FastAPI/Uvicorn directamente en la maquina de desarrollo. En ese modo, Compose puede aportar MediaMTX y, opcionalmente, PostgreSQL. SQLite funciona sin un contenedor de base de datos.

## Requisitos

- Docker Desktop con Docker Compose
- Python 3.12 recomendado para coincidir con la imagen del backend
- Node.js 22 y npm
- Acceso a las camaras RTSP o un emisor RTMP de prueba

## 1. Configurar variables locales

Desde la raiz del repositorio, crea el `.env` si aun no existe. No sobrescribas un `.env` que ya tenga credenciales reales:

```bash
[ -f .env ] || cp .env.example .env
```

El backend lee este archivo y Docker Compose lo usa para interpolar PostgreSQL. La plantilla usa nombres DNS internos para el stack completo; para esta guia manual, cambia `DATABASE_URL` a SQLite y `MEDIAMTX_API_URL` a `http://127.0.0.1:9997` como se muestra abajo. Configura el `MEDIAMTX_API_PASSWORD` para que coincida con el usuario `dashboard-api` de `mediamtx.yml`.

```env
DATABASE_URL=sqlite+aiosqlite:///./camera_dashboard.db
CORS_ORIGINS=http://localhost:5173
MEDIAMTX_API_URL=http://127.0.0.1:9997
MEDIAMTX_WEBRTC_PUBLIC_URL=http://localhost:8889
PERSON_DETECTION_ENABLED=false
ADMIN_USERNAME=admin
ADMIN_PASSWORD=local-admin-password
JWT_SECRET_KEY=replace-this-with-a-random-local-secret
```

El valor por defecto de `DATABASE_URL` usa SQLite. Como Uvicorn se ejecuta desde `backend/`, el archivo `camera_dashboard.db` queda en esa carpeta. `PERSON_DETECTION_ENABLED=false` evita descargar/cargar el modelo YOLO mientras se desarrolla el catalogo y la reproduccion.

Para usar PostgreSQL, agrega estas variables al mismo `.env` antes de iniciar Compose:

```env
POSTGRES_USER=camera
POSTGRES_PASSWORD=local-postgres-password
POSTGRES_DB=camera_dashboard
DATABASE_URL=postgresql+asyncpg://camera:local-postgres-password@127.0.0.1:5432/camera_dashboard
```

Usa estas credenciales solo para desarrollo local. No publiques las contrasenas de `.env` ni las reutilices en produccion.

## 2. Preparar MediaMTX con Compose

El archivo `mediamtx.yml` puede contener credenciales privadas. No lo reemplaces si ya existe. Si necesitas crearlo, copia la plantilla y sustituye los valores RTSP:

```bash
cp mediamtx.example.yml mediamtx.yml
```

Comprueba que el archivo tenga `api: yes`, WebRTC/HLS habilitado y una regla `all_others` con `source: publisher` para aceptar nombres RTMP variables. La plantilla define un usuario `dashboard-api`; configura su `pass` con el mismo valor de `MEDIAMTX_API_PASSWORD` en `.env`.

Inicia solo MediaMTX:

```bash
docker compose up -d mediamtx
docker compose logs -f mediamtx
```

El puerto de Control API `9997` esta vinculado a `127.0.0.1` en el host. No lo publiques en interfaces de red ni en Internet. El backend local consulta `http://127.0.0.1:9997/v3/paths/list`; para un publisher RTMP activo genera el WHEP URL que recibe el frontend.

Para probar la Control API desde otra terminal:

```bash
curl --user dashboard-api http://127.0.0.1:9997/v3/paths/list
```

`curl` solicita la clave de forma interactiva. Usa el valor de `MEDIAMTX_API_PASSWORD` definido en `.env`.

## 3. Elegir SQLite o PostgreSQL

### SQLite (por defecto)

No inicies ningun contenedor adicional. Mantén `DATABASE_URL=sqlite+aiosqlite:///./camera_dashboard.db` en `.env`.

### PostgreSQL opcional

El servicio PostgreSQL usa el volumen persistente `camera_db`. Inícialo sin iniciar el resto del stack:

```bash
docker compose up -d postgres
```

Configura `DATABASE_URL` con el host local, el puerto `5432` y el mismo usuario, clave y nombre de base indicados por `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`:

```env
DATABASE_URL=postgresql+asyncpg://camera:local-postgres-password@127.0.0.1:5432/camera_dashboard
```

El puerto PostgreSQL tambien esta limitado a loopback. El volumen conserva los datos al recrear el contenedor. No uses `docker compose down -v` si necesitas conservarlos.

## 4. Instalar y ejecutar FastAPI

En una terminal:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

FastAPI aplica `alembic upgrade head` automaticamente al arrancar y crea el usuario administrador si aun no existe. Para ejecutar la migracion manualmente, activa el entorno virtual, permanece en `backend/` y ejecuta:

```bash
alembic upgrade head
```

El primer usuario administrador usa `ADMIN_USERNAME` y `ADMIN_PASSWORD` de `.env`. Las rutas `/docs` y `/redoc` requieren iniciar sesion como administrador.

## 5. Instalar y ejecutar React/Vite

En otra terminal, desde la raiz del repositorio:

```bash
cd frontend
npm install
npm run dev
```

Vite inicia normalmente en http://localhost:5173. El frontend usa por defecto `http://localhost:8000/api/v1`; para cambiarlo, crea `frontend/.env.local` con:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

Reinicia Vite despues de cambiar `VITE_API_URL`. Para desarrollo desde otra maquina, ajusta tambien `CORS_ORIGINS`, `MEDIAMTX_WEBRTC_PUBLIC_URL` y `MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS` a valores alcanzables desde el navegador.

## 6. Verificar el entorno

- Dashboard: http://localhost:5173
- Health del backend: http://localhost:8000/health
- Documentacion API (requiere Admin): http://localhost:8000/docs
- MediaMTX HLS: http://localhost:8888
- MediaMTX WebRTC/WHEP: http://localhost:8889
- MediaMTX Control API local: http://127.0.0.1:9997/v3/paths/list

Las camaras RTSP se cargan desde `mediamtx.yml`. Los publishers RTMP/RTMPS activos se descubren mediante la Control API y pueden tardar hasta 10 segundos en aparecer en el frontend. El nombre completo del path es su identidad de acceso; si el emisor cambia el path, el dashboard lo tratara como otra camara.

Una publicacion H.265 puede aparecer en el catalogo y aun no reproducirse en ciertos navegadores. Para validar WebRTC en mas dispositivos, usa una entrada H.264 compatible. Esta configuracion no transcodifica el stream.

## Detener servicios

Deten MediaMTX y, si se inicio, PostgreSQL sin eliminar sus datos:

```bash
docker compose stop mediamtx
docker compose stop postgres
```

`docker compose down -v` elimina los volumenes locales de desarrollo; usalo solo si estas seguro de que ya no necesitas sus datos.