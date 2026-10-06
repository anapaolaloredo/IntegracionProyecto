# Microservicios con JWT

Seis servicios Flask independientes que comparten un mismo secreto (`JWT_SECRET_KEY`, alias `SECRET_KEY`) para firmar y validar
tokens JWT (módulo común en `apps/services/common`).

## Servicios y puertos

| Servicio  | Puerto | Función                                                                 |
|-----------|--------|-------------------------------------------------------------------------|
| `login`   | 5000   | Registro, login con 2FA, emisión de `session_token`/`refresh_token`, `/session/refresh`, logout real |
| `soap`    | 5001   | Servicio SOAP de libros (escrituras con JWT válido)                     |
| `users`   | 5002   | Usuarios con roles admin/cliente (`POST /api/users` solo admin)         |
| `authors` | 5003   | Autores y relación `libro_autor` (escritura solo admin)                 |
| `pedidos` | 5004   | Pedidos con stock transaccional y estados                               |
| `pagos`   | 5005   | Pagos; actualizan `pedidos.estado` en la misma transacción              |

## Variables de entorno (ver `.env.example` de cada servicio)

| Variable | Servicios | Notas |
|----------|-----------|-------|
| `JWT_SECRET_KEY` (alias `SECRET_KEY`) | todos | **Debe ser idéntica en los seis servicios**, si no los tokens se rechazan (401). `JWT_SECRET_KEY` tiene prioridad; si en un servicio se usa un nombre y en otro el otro con valores distintos, aparecen 401. Mínimo 32 caracteres; el servicio no arranca con el valor de ejemplo `change-me...`. |
| `REDIS_URL` | todos | `redis://:<password>@localhost:6379/0` (`rediss://` solo si Redis queda en otra máquina). Ver sección Redis. |
| `REDIS_TIMEOUT` | todos | Timeout de conexión/socket en segundos (por defecto 2). |
| `BOOKS_CACHE_TTL` | soap | TTL en segundos de la caché del catálogo (por defecto 60). |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | todos | `login` usa `auth_service_user`; el resto `library_user` en los ejemplos. |
| `PORT` | todos | Puerto de escucha (tabla anterior). |
| `CORS_ORIGINS` | soap, users, authors, pedidos, pagos | Orígenes separados por comas. En producción listar **solo** los clientes, nunca `*`. |
| `REFRESH_TTL_DAYS` | login | Vigencia del refresh token (ejemplo: 7). |
| `SESSION_TTL_MINUTES` | login | Vigencia del session token (ejemplo: 30). |
| `CODE_TTL_MINUTES`, `SMTP_*`, `LOCAL_MAILBOX_USER`, `MAIL_FROM` | login | Código 2FA por Postfix local (ver `login/README_POSTFIX.md`). |
| `LOG_TOKENS` | solo soap | `true` imprime el token Bearer en el log de cada escritura (evidencia de revisión). Poner `false` en producción. |

## Cómo correr cada servicio

```bash
cd apps/services/<servicio>        # login | soap | users | authors | pedidos | pagos
cp .env.example .env               # y ajustar valores (mismo JWT_SECRET_KEY en todos)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python app.py
```

Pruebas por servicio: `.venv/bin/python -m pytest tests -q` (el módulo común:
`cd apps/services && login/.venv/bin/python -m pytest common/tests -q`).

## Migraciones (orden obligatorio)

1. `data/library_schema.sql`
2. `data/migrations/2026-09-18_tablas_login.sql`
3. `data/migrations/2026-10-06_pedidos_pagos.sql`

> La migración de pedidos/pagos **no fue aplicada a ninguna base de datos** durante este trabajo;
> hay que ejecutarla y revisarla antes de usar `pedidos` y `pagos`.

## HTTPS y CORS

Los servicios hablan HTTP plano. HTTPS se termina en un proxy inverso (nginx o balanceador)
delante de ellos; Flask no maneja TLS. En producción, `CORS_ORIGINS` debe listar únicamente los
orígenes de los clientes.

## Redis (capa compartida)

PostgreSQL sigue siendo la fuente de datos. Redis guarda estado temporal (sesiones, refresh tokens,
jti revocados) y la caché pública del catálogo. Los seis servicios usan el mismo Redis.

### Claves y TTL

| Clave | Contenido | TTL |
|-------|-----------|-----|
| `jwt:revoked:<jti>` | marca de token revocado | lo que reste al token (mínimo 1 s) |
| `session:<jti>` | datos de la sesión de un access token (usuario, rol, `jti_refresh`, `exp_refresh`) | `SESSION_TTL_MINUTES` |
| `refresh:<jti>` | refresh token vigente (valor: id de usuario) | `REFRESH_TTL_DAYS` |
| `refresh_access:<jti_refresh>` | conjunto de los jti de access vivos de un login; sirve para que el logout los revoque todos | `REFRESH_TTL_DAYS` |
| `books:list:<hash>` | respuesta cacheada de un listado/búsqueda del catálogo | `BOOKS_CACHE_TTL` |
| `books:<isbn>` | respuesta cacheada de un libro | `BOOKS_CACHE_TTL` |

### Sesiones, refresh y logout

- `/login/verify` guarda `refresh:<jti>` y `session:<jti>`; si Redis falla responde 503 y el código 2FA
  no se consume.
- `/session/refresh` exige que el refresh token siga en Redis y no esté revocado.
- `/session/extend` emite un access token nuevo y **revoca el anterior**.
- `/logout` es un logout real: borra `session` y `refresh`, revoca todos los access jti del login
  (vía `refresh_access:*`) y el jti del refresh. Es seguro reintentar: si falla a medias, repetir
  con el mismo token termina el trabajo.
- Cada ruta protegida de cualquier servicio consulta `jwt:revoked:<jti>` en Redis.

### Modos de fallo

- **Fail-closed** (sesión, revocación, autorización): con Redis caído, las rutas protegidas y
  `/login/verify`, `/session`, `/session/extend`, `/session/refresh` y `/logout` responden **503**; nunca
  se acepta ni se emite un token sin poder consultarlo.
- **Fail-open** (caché del catálogo): el fallo se cuenta en `redis_errors_total` y se consulta PostgreSQL.
- Siguen funcionando con Redis caído: `/register`, `/login`, `/health`, `/metrics` y los GET del catálogo.
- Si la memoria de Redis se llena, con `noeviction` las escrituras fallan (503) en vez de expulsar claves.

### Redis en producción (GCP)

Producción usa el Redis que ya existe en la instancia de GCP, y los seis servicios corren en esa
misma instancia, así que `REDIS_URL=redis://:<password>@localhost:6379/0`. Requisitos en `redis.conf`:

- `bind 127.0.0.1`: solo escucha en localhost.
- `requirepass <password>`: contraseña obligatoria (la misma que va en `REDIS_URL`).
- `maxmemory-policy noeviction`: con la memoria llena las escrituras **fallan** (fail-closed) en vez de
  expulsar claves; con otra política Redis podría borrar `jwt:revoked:*` y un token revocado volvería a valer.
- **No abrir el puerto 6379 en el firewall de GCP.**
- `rediss://` (TLS) solo si algún día Redis queda en otra máquina.

Solo para desarrollo local: `cd apps/services && cp redis.env.example .env && docker compose up -d redis`
(el `docker-compose.yml` es solo de desarrollo), o bien
`brew install redis && redis-server --requirepass <password> --maxmemory 256mb --maxmemory-policy noeviction`.
Nunca versionar `.env` ni contraseñas reales.

### `/health` y `/metrics`

`GET /health` responde `{"servicio","status","db","redis"}` (503 solo si la BD falla).
`GET /metrics` (formato Prometheus) expone `cache_hits_total`, `cache_misses_total`,
`cache_invalidations_total`, `redis_errors_total`, `redis_latency_seconds_sum/count`,
`jwt_revocation_checks_total` y `jwt_rejected_total`.
**`/metrics` es público**: conviene restringirlo en el proxy inverso (por IP o red interna).

### Caché obsoleta

Un cambio de stock hecho por `pedidos` (o una escritura vía `soap`) invalida `books:*`. Un cambio hecho
**directo en PostgreSQL** no invalida nada y se verá tras como máximo `BOOKS_CACHE_TTL` segundos.

### Verificación de la capa Redis

Todo se verificó **solo con fakeredis**; **no se ejecutó nada contra un Redis real**. Las pruebas
opcionales contra Redis real (Task 8, `apps/services/common/tests/test_redis_real.py`) deben correrlas
ustedes **en la instancia de GCP**, porque allí Redis solo escucha en localhost. Hasta entonces esa
verificación está **pendiente**.

## Guía de humo con curl (solo documentación)

```bash
# 1) login (2FA): POST /register, POST /login, POST /login/verify?format=json  -> session_token + refresh_token
TOKEN=<session_token>
curl -s -X POST localhost:5004/api/pedidos -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"lineas":[{"id_libro":1,"cantidad":1}]}'                  # 201 (sin token: 401)
curl -s -X POST localhost:5005/api/pagos -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"id_pedido":<id>,"metodo":"tarjeta"}'                     # 201, pedido -> pagado
curl -s -X POST localhost:5003/api/authors -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"nombre_autor":"X"}'  # 403 con rol cliente
curl -s -X POST localhost:5000/session/refresh?format=json -H "Content-Type: application/json" \
     -d '{"refresh_token":"<refresh_token>"}'                       # nuevo session_token
```

## Estado de verificación y limitaciones conocidas

- Las suites unitarias de todos los servicios, `common` y el núcleo de `desktop_app` pasan (ver
  `AI_CHANGELOG`). Las pruebas de la capa Redis se hicieron **solo con fakeredis**.
- **La prueba de humo de punta a punta contra una base de datos real NO se ejecutó** (ni Postfix/SMTP).
  La guía de curl anterior es solo documentación.
- Los cambios de UI del cliente de escritorio solo se comprobaron con `py_compile`, no se ejecutaron.
- Los GRANTs de la migración a `library_user` son amplios (DML completo sobre `cuentas`, incluida
  `contrasena_hash`, `autores`, `libro_autor`, y UPDATE sobre `libros`) porque todos los servicios
  comparten un solo rol de BD. Seguimiento recomendado: un rol por servicio con permisos mínimos.
- El logout ya no es sin estado: es un logout real respaldado por Redis (ver sección Redis).

## Permisos de soap (libros)

`POST /api/libros` y `DELETE /api/libros/<isbn>` exigen JWT con rol **admin** (403 para `cliente`). `PUT /api/libros/<isbn>` acepta cualquier JWT de acceso válido. Las lecturas (GET) son públicas.
