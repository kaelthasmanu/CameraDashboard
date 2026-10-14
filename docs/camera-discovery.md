# Descubrimiento y visualizacion de camaras

## Objetivo actual

El backend conserva las camaras RTSP configuradas en `mediamtx.yml` y agrega las publicaciones RTMP/RTMPS que MediaMTX reporta activas. La respuesta sigue siendo el contrato existente de `GET /api/v1/cameras`, por lo que el frontend reproduce ambos tipos mediante WHEP.

## Flujo de captura

1. `backend/app/infrastructure/camera_repository.py` lee `paths` del YAML al iniciar. Omite previews como camaras independientes y empareja `<nombre>_preview` con su path principal. Las entradas `source: publisher` no se agregan desde el YAML, porque son plantillas y pueden no tener emisor conectado.
2. En cada solicitud al catalogo, el repositorio consulta `GET /v3/paths/list` de la Control API de MediaMTX. Sigue todas las paginas que devuelva la API.
3. Agrega paths que esten online y cuyo source sea `rtmpConn` o `rtmpsConn`. Un path offline, un source RTSP no configurado y `*_preview` no se agregan como camaras dinamicas.
4. Para la publicacion `live/liveStream_AC0A7CCPAJ5E6AB_0_0`, el backend genera `http://<host>:8889/live/liveStream_AC0A7CCPAJ5E6AB_0_0/whep`. El nombre completo del path es la identidad, aunque cambie el sufijo aleatorio de `liveStream`.
5. Cada path dinamico obtiene un ID entero deterministico basado en SHA-256 del nombre. No cambia por el orden de la respuesta ni por reiniciar el backend. Los IDs de RTSP mantienen el orden existente del YAML.
6. `GET /api/v1/cameras` aplica los permisos de usuario existentes por nombre. El hook `useCameras` actualiza el catalogo cada 10 segundos, sin mostrar el estado de carga en cada refresco.

Si la Control API no responde, el backend registra un warning y entrega las camaras estaticas disponibles. Asi un problema temporal de descubrimiento no elimina el catalogo RTSP.

## Configuracion de MediaMTX

Habilitar la Control API en `mediamtx.yml`:

```yaml
api: yes
apiAddress: :9997
authInternalUsers:
  - user: dashboard-api
    pass: REPLACE_WITH_MEDIAMTX_API_PASSWORD
    ips: []
    permissions:
      - action: api
        path: ""

paths:
  all_others:
    source: publisher
```

`all_others` aplica defaults a nombres de path que no tengan una entrada explicita. Las entradas fijas `camara_rtmp_1` y `camara_rtmp_2` no son necesarias para nombres variables; se pueden retirar si no se usan para otros emisores. MediaMTX escucha en `9997`; el `docker-compose.yml` de este proyecto publica ese puerto solo en loopback (`127.0.0.1`). No se debe publicar abiertamente en Internet.

El backend usa estos parametros, configurables por variables de entorno:

| Variable | Valor por defecto | Uso |
| --- | --- | --- |
| `MEDIAMTX_API_URL` | `http://localhost:9997` | URL base de Control API |
| `MEDIAMTX_API_USERNAME` | vacio | Usuario API; necesario para la configuracion protegida de Compose |
| `MEDIAMTX_API_PASSWORD` | vacio | Clave API; debe coincidir con el usuario definido en `mediamtx.yml` |
| `MEDIAMTX_API_TIMEOUT_SECONDS` | `2.0` | Timeout de consulta |
| `MEDIAMTX_WEBRTC_PUBLIC_URL` | `http://localhost:8889` | Base WHEP visible desde el navegador |

Si el backend corre en el mismo host, `http://localhost:9997` usa el binding loopback. Si corre en otro contenedor de la misma red Docker, configurar `MEDIAMTX_API_URL=http://mediamtx:9997`; en ese caso no hace falta publicar el puerto API en el host, y se recomienda eliminar el mapeo loopback si no se necesita acceso desde el host.

Restringir la Control API a la red privada del backend y configurar un usuario MediaMTX con permiso `api` cuando el backend no acceda desde localhost. Las credenciales del publisher RTMP tambien deben protegerse; no habilitar publicacion anonima si la red no es de confianza.

Verificacion local:

```sh
curl --user dashboard-api http://127.0.0.1:9997/v3/paths/list
```

`curl` solicita la clave de forma interactiva. No la agregues literalmente al comando ni la publiques en el historial del shell.

La respuesta debe incluir el path online y un source de tipo `rtmpConn` o `rtmpsConn`. Tambien comprobar `GET /api/v1/cameras` y que la `stream_url` publicada termine en `/whep`.

## Limitaciones conocidas

- El ID dinamico es estable y numerico, pero derivado del nombre del path; existe una posibilidad teorica de colision de hash. Si los IDs se convierten en referencias persistentes de base de datos, migrar a un registro persistente de nombres/IDs y gestionar colisiones de forma transaccional.
- Si el emisor cambia el path entre conexiones, se considera otra camara. Para un inventario duradero conviene guardar una asociacion entre identidad de dispositivo y path, o permitir alias editables.
- Las camaras RTMP dinamicas no tienen stream de preview/substream; la cuadricula y la vista ampliada usan el mismo stream.
- El backend no solicita `runOnReady` ni hooks para la deteccion inmediata; el frontend puede tardar hasta 10 segundos en mostrar una publicacion nueva.
- El backend no transcodifica. Un publisher H.265 puede no reproducirse en ciertos navegadores aunque WHEP responda; validar compatibilidad y publicar H.264 cuando se necesite soporte amplio.
- No se modifica la deteccion de personas. Su servicio actual espera fuentes RTSP y se inicia con las fuentes estaticas; para RTMP habria que definir ciclo de vida, URL RTSP de lectura, reintentos y recursos del modelo.
- El catalogo dinamico representa publishers online, no un inventario historico: al desconectarse, la camara desaparece de la lista actual.

## Siguientes mejoras

1. Persistir inventario y alias de camaras, asignando IDs secuenciales y unicos desde la base de datos en lugar de derivarlos del hash.
2. Incorporar eventos de disponibilidad de MediaMTX o un cache con reconciliacion para reducir consultas y acelerar altas/bajas.
3. Guardar protocolo, estado y hora de ultima conexion; mostrar estado offline durante un periodo configurable en lugar de retirar inmediatamente la camara.
4. Gestionar preview/substream para publishers y validar los codecs de entrada frente a WebRTC/HLS.
5. Definir y probar la politica de acceso para camaras dinamicas nuevas, incluyendo asignacion por rol y restricciones de publicacion.
6. Integrar deteccion de personas solo despues de definir como consumir RTMP publicado, como parar/reiniciar tareas cuando cambian los publishers y como limitar CPU/GPU.
7. Agregar pruebas de integracion contra la version fijada de MediaMTX, incluyendo autenticacion, paginacion, caidas de API y ciclo de conexion/desconexion.