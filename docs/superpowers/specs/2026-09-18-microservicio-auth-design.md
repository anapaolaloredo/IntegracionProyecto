# Diseño: Microservicio de autenticación (`apps/services/login`)

Fuente: `05_prompt_microservicio_auth.md` + aclaraciones en conversación (2026-09-18).

## 1. Objetivo

Microservicio Flask + Psycopg 3 + PostgreSQL, independiente del monolito
(`apps/web-monolito01`), que registra usuarios, autentica con segundo factor
por correo (2FA), y expone sesiones de 30 minutos. Responde XML (default) o
JSON según `?format=`. No hace llamadas HTTP hacia/desde el monolito; solo
comparte la base de datos física `library`.

## 2. Arquitectura y componentes

- **Servicio:** `apps/services/login/`, mismo patrón de capas que
  `apps/services/library_soap_service` (`config/`, `db/`, `app.py`,
  `requirements.txt`, `.env`, `.env.example`, `README.md`).
- **Puerto:** 5000.
- **Rol de BD:** `auth_service_user`, mínimo privilegio, análogo a
  `soap_service_user`, con permisos solo sobre las tablas que le tocan
  (`usuarios`, `personas`, `codigos_verificacion`, `sesiones`).
- **Correo (2FA):** Postfix instalado a nivel de sistema operativo en la
  misma instancia de GCP, configurado **solo para entrega local**
  (`mydestination = localhost, <hostname-instancia>`, sin relay externo).
  Todos los códigos 2FA llegan a **un único buzón local** (el usuario del
  sistema con el que se hizo SSH a la instancia); el correo registrado y el
  código van en el asunto/cuerpo para identificar a quién pertenece cada
  código, porque solo hay un tester y no se justifica un buzón por usuario
  (YAGNI). El usuario del sistema destino es configurable vía
  `.env` (`LOCAL_MAILBOX_USER`), no hardcodeado. Flask envía por `smtplib` a `localhost:25`, sin autenticación ni
  TLS (todo el tráfico es loopback). Nada de este flujo sale de la instancia
  ni depende de un proveedor externo (Gmail, SendGrid, etc.) — cumple el
  requisito del profesor de "SMTP propio, local, no externo".
- **Monolito:** se actualiza su modelo/controlador/vistas de usuarios para
  seguir funcionando contra el esquema normalizado (ver sección 6), pero
  sigue siendo un sistema aparte: comparte la base de datos, no el código.

## 3. Modelo de datos

Se normaliza `usuarios` en dos tablas (1:1 por `id_usuario`), más dos tablas
propias del microservicio:

```sql
-- Reemplaza a la usuarios actual (se quita nombre_usuario)
usuarios (
  id_usuario       SERIAL PRIMARY KEY,
  correo           VARCHAR(150) NOT NULL UNIQUE,
  contrasena_hash  VARCHAR(255) NOT NULL,
  rol              VARCHAR(10)  NOT NULL DEFAULT 'cliente' CHECK (rol IN ('admin','cliente')),
  fecha_registro   TIMESTAMP    NOT NULL DEFAULT now()
)

-- Nueva, 1:1 con usuarios
personas (
  id_usuario        INT PRIMARY KEY REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  nombre            VARCHAR(100) NOT NULL,
  apellido_paterno  VARCHAR(100) NOT NULL,
  apellido_materno  VARCHAR(100) NOT NULL
)

-- Propia del microservicio de login
codigos_verificacion (
  id_codigo    SERIAL PRIMARY KEY,
  id_usuario   INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  codigo_hash  VARCHAR(255) NOT NULL,
  expira_en    TIMESTAMP NOT NULL,
  usado        BOOLEAN NOT NULL DEFAULT false,
  creado_en    TIMESTAMP NOT NULL DEFAULT now()
)

-- Propia del microservicio de login
sesiones (
  token        VARCHAR(64) PRIMARY KEY,
  id_usuario   INT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
  creada_en    TIMESTAMP NOT NULL DEFAULT now(),
  expira_en    TIMESTAMP NOT NULL
)
```

Se conservan tal cual (no dependen de `nombre_usuario`):
`usuarios_auditoria_rol`, `trg_usuarios_auditoria_rol`,
`uq_usuarios_admin_unico`.

**Migración** (script nuevo en `data/`, no se reescribe `library_schema.sql`
desde cero):
1. Crear `personas`, `codigos_verificacion`, `sesiones`.
2. Copiar `nombre_usuario` → `personas.nombre` para las filas existentes
   (apellidos quedan vacíos/placeholder, a rellenar manualmente para los 30
   usuarios semilla — son datos de prueba, no de producción).
3. Eliminar la columna `usuarios.nombre_usuario` y su índice/constraint
   asociado.
4. Actualizar `fn_crear_usuario` / `fn_actualizar_usuario` en
   `data/library_schema.sql` para reflejar el nuevo esquema.

## 4. Endpoints

Todos aceptan `?format=json`; sin el parámetro, XML es el default.

| Método | Ruta | Body/Header | Éxito | Error |
|---|---|---|---|---|
| POST | `/register` | `{nombre, apellido_paterno, apellido_materno, email, password}` | `201 {id_usuario}` | `400` (campo faltante, email inválido, password < 8) / `409` (email duplicado) |
| POST | `/login` | `{email, password}` | `200 {pendiente_verificacion: true}` (genera código, lo hashea, guarda con expiración de 5 min, lo envía por Postfix local) | `401` credenciales inválidas (mensaje genérico) |
| POST | `/login/verify` | `{email, codigo}` | `200 {session_token}` (crea fila en `sesiones`, `expira_en = now()+30min`) | `401` código inválido o expirado |
| POST | `/logout` | header `Authorization: Bearer <token>` | `200` (borra la fila de `sesiones`) | `401` sin token o token inválido |
| GET | `/session` | header opcional `Authorization: Bearer <token>` | siempre `200`; `{autenticado: true, id_usuario, email, nombre}` o `{autenticado: false}` | — (no es una acción protegida, es una consulta de estado) |
| GET | `/health` | — | `200 {status:"ok", db:"ok"}` (hace `SELECT 1`) | `503` si falla la conexión a Postgres |

## 5. Seguridad

- Password y código 2FA: hasheados con `werkzeug.security.generate_password_hash`
  (mismo enfoque que ya usa `library_soap_service`), nunca texto plano.
- Password mínimo 8 caracteres.
- Email: validado por formato (regex) + `UNIQUE` en BD.
- Token de sesión: `secrets.token_hex(32)` (256 bits), vida fija de 30 min
  desde su creación (no se renueva con actividad).
- Código 2FA: 6 dígitos numéricos, expira a los 5 minutos, un solo uso
  (`usado`).

## 6. Cambios en el monolito

Archivos ya localizados que requieren cambio:

- `data/library_schema.sql`: `fn_crear_usuario` / `fn_actualizar_usuario`
  cambian de `p_nombre_usuario` a los datos de `personas`.
- `apps/web-monolito01/src/models/usuarioModel.js`: quitar
  `obtenerPorNombreUsuario`; `crear`/`actualizar` reciben nombre/apellidos e
  insertan/actualizan en `usuarios` + `personas`.
- `apps/web-monolito01/src/controllers/authController.js`: `registrar()` deja
  de pedir `nombre_usuario` y de chequear duplicado de username.
- `apps/web-monolito01/src/views/auth/registro.ejs`,
  `views/usuarios/editar.ejs`, `views/usuarios/listar.ejs`,
  `views/partials/header.ejs`: cambian el campo "nombre de usuario" por
  nombre/apellidos.
- El login del monolito (`authController.iniciarSesion`) no cambia de forma
  (correo + contraseña); el 2FA es exclusivo del microservicio nuevo, el
  monolito no lo usa.

## 7. Documentación (Swagger)

`flasgger` documentando los 6 endpoints (incluye `/login/verify`), con
ejemplos de request/response en XML y JSON en la descripción de cada uno
(Swagger UI no negocia XML nativamente, se documenta como ejemplo de texto).

## 8. Validación end-to-end

Script de pruebas manuales (`apps/services/login/tests/pruebas_manuales.py`,
mismo patrón que ya existe en `library_soap_service/tests/`) que ejecuta
contra la instancia real: registro → login → leer el código en el buzón
local (`mail` / lectura de `/var/mail/<usuario>` por SSH, paso manual) →
verify → session (autenticado:true) → logout → session otra vez
(autenticado:false) — cada paso probado en XML y en JSON.

## 9. Fuera de alcance

- No se implementa recuperación de contraseña, ni edición/borrado de cuenta
  desde este microservicio (no pedido en el prompt).
- No se implementa reenvío de código 2FA (si expira, el usuario repite
  `POST /login` para generar uno nuevo).
- No se toca la lógica de compra/catálogo del monolito.
