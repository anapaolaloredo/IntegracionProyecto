# Reflexión: Redis y JWT en los microservicios de Library

## 1. Por qué usar Redis en los microservicios

Un JWT firmado es *stateless*: cualquier servicio puede verificarlo con la clave compartida sin consultar a nadie. Eso es justo su ventaja, pero también su problema: **un token válido sigue siendo válido hasta que expira**, aunque el usuario ya haya cerrado sesión o le hayan quitado el acceso. Con seis procesos independientes (login, libros, users, authors, pedidos y pagos), ninguno puede "olvidar" un token por su cuenta, y la memoria de un proceso no la ve el otro.

Redis resuelve eso con un estado **pequeño, compartido y con expiración automática**:

- **Revocación inmediata.** Al hacer logout se guarda `jwt:revoked:<jti>` con un TTL igual a lo que le quedaba de vida al token. Cada servicio consulta esa clave antes de aceptar un JWT, así que el token deja de servir en los seis a la vez. La clave se borra sola cuando el token habría expirado de todos modos: la lista de revocados nunca crece sin límite.
- **Sesiones y refresh tokens con TTL.** `session:<jti>` (30 min) y `refresh:<jti>` (7 días) permiten que `/session`, `/session/extend` y `/session/refresh` validen contra un estado real, y que `/logout` cierre todo el inicio de sesión (incluidos los tokens de acceso hermanos) con una operación.
- **Caché de lecturas públicas.** El catálogo de libros se consulta mucho y cambia poco. `books:list:<hash>` y `books:<isbn>` evitan ir a PostgreSQL en cada lectura, con TTL corto y borrado explícito al escribir.
- **Velocidad.** En la medición real de la instancia, cada consulta de revocación tardó en promedio **0.4 ms** (5 consultas en 2.2 ms), y Redis reportó ~8 µs por `GET` y ~18 µs por `SET`. Validar la revocación en cada petición casi no cuesta nada.

**Lo que Redis NO es aquí:** la fuente de verdad. PostgreSQL sigue guardando usuarios, libros, pedidos y pagos. Redis solo guarda estado efímero y derivado; si se pierde, no se pierden datos del negocio (el peor caso es que los usuarios tengan que iniciar sesión otra vez).

### Qué pasa cuando Redis falla (decisión de diseño)

No todo falla igual, y es deliberado:

| Función | Si Redis no está disponible | Por qué |
|---|---|---|
| Sesión, refresh, revocación y autorización | **Falla cerrado**: responde 503 y no acepta el token | Aceptar un token sin poder comprobar si fue revocado reabriría el hueco de seguridad que Redis cierra |
| Caché del catálogo | **Falla abierto**: se consulta PostgreSQL directamente | Es solo una optimización; la lectura pública no debe depender de Redis |
| `/register`, `/login`, `/health`, `/metrics`, lecturas públicas | Siguen funcionando | No se debe "sobreproteger": que Redis caiga no puede impedir registrarse ni iniciar el flujo de login |

## 2. Qué endpoints son adecuados para JWT y para Redis

El criterio: **JWT donde se modifica o se consulta información privada; Redis donde hay que recordar estado entre peticiones o evitar trabajo repetido; nada de ambos donde el endpoint debe ser accesible para empezar a usar el sistema.**

| Endpoint | ¿JWT? | ¿Redis? | Razón |
|---|---|---|---|
| `POST /register` | No | No | Es la puerta de entrada; debe funcionar sin sesión ni Redis |
| `POST /login` | No | No | Valida credenciales y envía el código 2FA |
| `POST /login/verify` | No (usa el código 2FA) | **Sí** (crea `session:` y `refresh:`) | Si Redis falla no se entrega ningún token (503) y el código 2FA no se gasta |
| `GET /session` | Sí | **Sí** | Valida el token contra la sesión guardada |
| `POST /session/extend` | Sí | **Sí** | Emite un token nuevo y revoca el anterior |
| `POST /session/refresh` | Refresh token | **Sí** | Exige que el refresh siga vigente en Redis |
| `POST /logout` | Sí | **Sí** | Borra sesión y refresh y escribe `jwt:revoked:` |
| `GET /health`, `GET /metrics` | No | Solo lo consulta (reporta `redis: ok/error`) | Monitoreo; no puede exigir sesión |
| `GET /api/libros`, `/buscar`, `/temas`, `/catalogo`, `/{isbn}` | No | **Caché** (opcional) | Lecturas públicas, repetitivas y baratas de cachear |
| `POST /api/libros`, `DELETE /api/libros/{isbn}` | **Sí, solo admin** | Revocación + **invalida caché** | Escrituras sensibles |
| `PUT /api/libros/{isbn}` | Sí (cualquier rol válido) | Revocación + **invalida caché** | Edición de existencias |
| `GET /api/roles`, `GET /api/authors[/{id}]` | No | No | Catálogos públicos de solo lectura |
| `POST/PATCH/DELETE /api/authors…` | **Sí, solo admin** | Revocación | Escrituras |
| `/api/users…` | **Sí** (admin: todos; cliente: solo el suyo) | Revocación | Datos personales |
| `/api/pedidos…` | **Sí** (cada quien ve los suyos; admin todos) | Revocación; crear o cancelar **invalida `books:*`** | El stock cambia y el catálogo cacheado quedaría viejo |
| `/api/pagos…` | **Sí** (reembolso solo admin) | Revocación | Dinero y estado del pedido |

**Qué no se pone en Redis:** los pedidos, los pagos y los usuarios. Son transacciones que necesitan consistencia (`SELECT … FOR UPDATE` en PostgreSQL para descontar stock y marcar un pedido como pagado en la misma transacción). Tampoco se guardan contraseñas ni tokens completos: solo identificadores (`jti`).

## 3. Cómo se implementa

**Un solo módulo compartido** (`apps/services/common`) que usan los seis servicios:

- `jwt_auth.py`: crea y valida tokens HS256 (firma, algoritmo fijo, expiración, `user_id`, `role_id`, `type` y `jti`). El decorador `@requiere_jwt(roles=…)` aplica el orden **firma/claims (401) → revocación en Redis (401 si está revocado, 503 si Redis no responde) → rol (403)**.
- `redis_store.py`: cliente único desde `REDIS_URL` (con contraseña), timeouts de 2 s, reconexión y las funciones de sesión, refresh, revocación y caché.
- `JWT_SECRET_KEY` idéntica en los seis `.env`, nunca en el código.

**Flujo de una sesión:**

1. `POST /login` valida credenciales y manda un código 2FA al buzón local.
2. `POST /login/verify` valida el código; emite un JWT de acceso de **30 minutos** y un refresh de **7 días**, y los registra en Redis (`session:<jti>`, `refresh:<jti>`, `refresh_access:<jti>`).
3. En cada petición protegida, el servicio verifica la firma y consulta `EXISTS jwt:revoked:<jti>`; después comprueba el rol.
4. `POST /session/extend` y `/session/refresh` emiten un token nuevo antes de caducar; el anterior se revoca.
5. `POST /logout` borra la sesión y el refresh, y revoca todos los tokens de acceso de ese inicio de sesión con TTL restante.

**Flujo del caché (cache-aside):** un `GET` del catálogo busca `books:<isbn>` o `books:list:<hash de filtros>` en Redis; si no está, consulta PostgreSQL, guarda la respuesta con TTL (60 s por omisión, `BOOKS_CACHE_TTL`; 300 s en esta instalación) y la devuelve. Cualquier `POST`, `PUT` o `DELETE` exitoso de libros, y crear o cancelar un pedido, borra `books:*`. La respuesta trae la cabecera `X-Cache: HIT` o `MISS`.

**Seguridad de Redis:** escucha solo en `127.0.0.1`, exige contraseña (`requirepass`), el puerto 6379 no se abre en el firewall, y la política `maxmemory-policy noeviction` hace que, si la memoria se llena, las escrituras fallen en vez de borrar claves de sesión o revocación en silencio.

**Observabilidad:** `GET /health` en cada servicio (con `db` y `redis`), `GET /metrics` con `jwt_revocation_checks_total`, `jwt_rejected_total`, `redis_latency_seconds` y `cache_invalidations_total`, y la app de escritorio muestra el estado de Redis junto a los semáforos.

## 4. Claves que Redis guarda (tabla)

| Clave | Contenido | TTL | La crea | Se borra cuando |
|---|---|---|---|---|
| `session:<jti_acceso>` | JSON con `user_id`, `role_id`, `email`, `jti_refresh`, `exp_refresh` | 30 min (`SESSION_TTL_MINUTES`) | `login/verify`, `session/extend`, `session/refresh` | Expira, hace `/logout` o se extiende |
| `refresh:<jti_refresh>` | `user_id` | 7 días (`REFRESH_TTL_DAYS`) | `login/verify` | Expira o hace `/logout` |
| `refresh_access:<jti_refresh>` | Conjunto de los `jti` de acceso vivos de ese inicio de sesión | 7 días | Cada emisión de acceso | Expira o hace `/logout` |
| `jwt:revoked:<jti>` | Marca de revocado | Lo que le quedaba al token (≤ 30 min si es de acceso, ≤ 7 días si es refresh) | `/logout`, `/session/extend` | Expira sola |
| `books:list:<hash>` | Respuesta XML del listado o de una búsqueda con esos filtros | 60 s por omisión (300 s aquí) | Primer `GET` (MISS) | Expira o cualquier escritura de libros o pedidos |
| `books:<isbn>` | Respuesta XML de un libro | 60 s por omisión (300 s aquí) | Primer `GET` por ISBN | Expira o cualquier escritura de libros o pedidos |

## 5. Evidencia medida en la instancia

| Observación | Valor | Qué demuestra |
|---|---|---|
| `TTL session:…` | 1299 s | Sesión con vida de 30 min corriendo |
| `TTL refresh:…` | ≈ 600 000 s | Refresh de 7 días |
| `TTL jwt:revoked:…` (acceso) | 742 s | La revocación dura solo lo que le quedaba al token |
| `TTL jwt:revoked:…` (refresh) | 601 270 s | La revocación de un refresh dura ~7 días |
| `SET books:… EX 300` | TTL 300 s | El caché usa `BOOKS_CACHE_TTL` |
| `SCAN books:*` + `UNLINK books:…` tras una escritura | 5 claves borradas | Invalidación al modificar |
| `GET` + `SET` del mismo `books:…`, y luego solo `GET` | MISS → HIT | Cache-aside funcionando |
| `EXISTS jwt:revoked:<jti>` antes de cada petición | Cada petición protegida | Verificación de revocación en cada servicio |
| `jwt_revocation_checks_total` (users) | 5 | Contador de consultas de revocación |
| `redis_latency_seconds` | 0.0022 s / 5 consultas ≈ **0.4 ms** | Costo mínimo por validación |
| `total_commands_processed` | 2 493 | Actividad acumulada de Redis |
| `expired_keys` | 28 | Los TTL expiran claves solos |
| `evicted_keys` | **0** | La política `noeviction` se respeta |
| `Token revocado` (401) en users, authors, pedidos, pagos y soap tras `/logout` | 401 en los cinco | La revocación es compartida por todo el sistema |
| `/health` con `"redis":"ok"` en los seis servicios | 6 de 6 | Todos conectados al mismo Redis |

(Nota: `keyspace_misses` incluye las consultas `EXISTS jwt:revoked:…` que devuelven 0 cuando el token **no** está revocado, que es el caso normal; no es una tasa de fallos del caché.)

## 6. Limitaciones y decisiones abiertas

- **Persistencia.** Si Redis reinicia sin persistencia (AOF/RDB), se pierden las revocaciones: un token cerrado con `/logout` volvería a ser válido hasta que expire (máx. 30 min), y los usuarios tendrían que iniciar sesión de nuevo. Activar AOF lo reduce.
- **Vigencia del token de acceso.** Está en 30 minutos (`SESSION_TTL_MINUTES`); es configurable si se requiere un valor distinto (el enunciado menciona 20).
- **Authors y el caché.** Vincular o desvincular un libro de un autor no invalida `books:*`; el catálogo puede mostrar autores desactualizados hasta que expire el TTL.
- **Tokens en logs.** El servicio de libros imprime los JWT en su registro (`LOG_TOKENS=true`) para poder revisar las transacciones; en producción debe ir en `false`.
- **HTTPS.** Pendiente del certificado; la app de escritorio ya trae el selector http/https.
- **Alcance de los contadores.** Las métricas viven en memoria y se reinician con cada arranque del servicio; para históricos haría falta Prometheus.
