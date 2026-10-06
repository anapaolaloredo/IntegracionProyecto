# Microservicios Users, Authors, Pedidos y Pagos con JWT — Diseño

Fecha: 2026-10-06

## Objetivo

Agregar cuatro microservicios (Users, Authors, Pedidos, Pagos) a `apps/services` y migrar `login` y `soap` de tokens de sesión opacos a JWT firmado, de forma que todas las operaciones de escritura exijan `Authorization: Bearer <JWT>` sin romper a los clientes actuales (Electron, escritorio PySide6).

## Decisiones acordadas

- `users` va separado de `login`. `login` solo autentica y emite tokens.
- JWT firmado HS256 con `SECRET_KEY` tomada del entorno (sin valor por defecto en código), compartida por todos los servicios.
- Vigencia del token de acceso: 30 min. Refresh token de 7 días.
- Roles: solo `admin` y `user` (hoy `cliente` en la base de datos). Sin tabla `roles`. Se conserva el índice de un solo admin. Mapeo fijo: `admin=1`, `user=2`.
- Sin lista de revocación, sin HTTPS dentro de Flask (se resuelve en un proxy), sin extras que no cambien el funcionamiento.
- `soap` conserva la impresión del token en logs porque el profe la usa para revisar transacciones, ahora controlada por `LOG_TOKENS` (por defecto `true` para no cambiar el comportamiento actual).
- CORS configurable con `CORS_ORIGINS`; el valor por defecto en desarrollo no cambia el comportamiento actual. En producción se fijan los orígenes de los clientes.
- Validación compartida en `apps/services/common/jwt_auth.py`.
- Pagos actualiza `pedidos.estado` directamente en la base `library`, en la misma transacción que inserta el pago.
- Stack: Flask sin blueprints, solo `psycopg`, Swagger con flasgger, `.env` por servicio.

## Estructura

| Servicio | Puerto | Responsabilidad |
|---|---|---|
| `login` (existe) | 5000 | 2FA, emite JWT y refresh token |
| `soap` (existe) | 5001 | CRUD de libros; valida JWT local |
| `users` | 5002 | Usuarios, roles, correos y contraseñas |
| `authors` | 5003 | Autores y relación `libro_autor` |
| `pedidos` | 5004 | Pedidos, líneas, stock y estados |
| `pagos` | 5005 | Pagos y paso del pedido a `pagado` |

Todos usan la base de datos `library`.

## Módulo compartido `common/jwt_auth.py`

- `crear_token(user_id, role_id, tipo, ttl)` y `decodificar(token, tipo)`.
- Claims: `user_id`, `role_id`, `type` (`access` o `refresh`), `iat`, `exp`.
- La decodificación fija `algorithms=["HS256"]` y exige `exp`, `user_id`, `role_id` y `type`. Rechaza `alg: none`, firmas falsas, tokens expirados y un refresh usado como acceso.
- Decorador `@requiere_jwt(roles=None)`: 401 si el token falta o es inválido, 403 si el `role_id` no está en `roles`. Deja `user_id` y `role_id` disponibles en `flask.g`.
- Nunca registra contraseñas; los tokens solo se registran si el servicio lo habilita (`LOG_TOKENS`, solo `soap`).
- Si `SECRET_KEY` no está definida, el servicio no arranca.

## Cambios en `login`

- `/login/verify` devuelve `session_token` (JWT de acceso, mismo nombre de campo) y `refresh_token`.
- `GET /session` valida el JWT sin consultar la base de datos.
- `POST /session/extend` emite un JWT de acceso nuevo si el actual sigue vigente.
- `POST /session/refresh` canjea un refresh token por un JWT de acceso nuevo.
- `POST /logout` responde 200. No invalida el token, que vive hasta expirar.
- `SESSION_TTL_MINUTES` se mantiene en 30. La tabla de sesiones queda sin uso.

## Permisos

- GET públicos: catálogo de libros y autores.
- GET con JWT: usuarios, pedidos y pagos. Un `user` ve solo lo suyo; un `admin` ve todo.
- Todo POST, PUT, PATCH y DELETE exige JWT.
- Solo `admin`: escribir en autores, borrar usuarios o cambiar su rol, y cambiar estados de pedido que no sean el pago.
- Un `user` puede crear pedidos y pagos propios y editar su propio perfil y contraseña.

## Pedidos y Pagos

Tablas nuevas: `pedidos`, `lineas_pedido`, `pagos`.

- Crear pedido: una transacción que bloquea los libros con `SELECT … FOR UPDATE`, valida el stock, lo descuenta y guarda el pedido con sus líneas. Si falta stock, rollback y 409.
- Estados: `pendiente → pagado → enviado`, y `cancelado`. Cancelar un pedido `pendiente` devuelve el stock.
- Registrar pago: una transacción que inserta en `pagos` y pone `pedidos.estado = 'pagado'`. Solo si el pedido está `pendiente` y es del usuario; si no, 409.

## Cambios en lo existente

- `soap` valida con `common` en lugar de llamar a `login /session`.
- El cliente de escritorio guarda el `refresh_token` y lo usa al recibir un 401. El Electron app no maneja sesión hoy y no cambia.
- Antes de implementar `users` hay que confirmar si `login` usa `cuentas`/`personas` (no están en ningún `.sql` del repo) o `usuarios`, y alinear el esquema.

## Pruebas

pytest por servicio: sin token (401), token expirado (401), firma falsa (401), `alg: none` (401), refresh como acceso (401), `user` en ruta de `admin` (403), flujo de refresh, transacción de pedido con stock insuficiente (409) y concurrencia sobre el stock.

## Fuera de alcance

HTTPS en Flask, revocación de tokens, tabla `roles`, cambios al Electron app.
