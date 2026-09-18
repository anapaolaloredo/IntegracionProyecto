# Diseño: Microservicio de autenticación (`apps/services/login`)

Fuente: `05_prompt_microservicio_auth.md` + aclaraciones en conversación (2026-09-18).

## 1. Objetivo

Microservicio Flask + Psycopg 3 + PostgreSQL, independiente del monolito
(`apps/web-monolito01`), que registra usuarios, autentica con segundo factor
por correo (2FA), y expone sesiones de 30 minutos. Responde XML (default) o
JSON según `?format=`. No hace llamadas HTTP hacia/desde el monolito, y
**no toca ninguna tabla del monolito** (usa tablas propias en la misma base
de datos física `library` — ver sección 3).

> **Actualización 2026-09-18:** la primera versión de este documento
> normalizaba la tabla `usuarios` del monolito (dividiéndola en
> `usuarios`+`personas`) y requería actualizar el monolito para que
> siguiera funcionando. Se descartó esa vía por costo/tiempo — mientras se
> implementaba apareció una vista (`vista_administradores`) que dependía de
> la columna a eliminar. Se sustituyó por tablas nuevas e independientes
> (`cuentas`/`personas`/`codigos_verificacion`/`sesiones`), sin tocar el
> monolito en absoluto. Las secciones 3 y 6 reflejan ya la versión vigente.

## 2. Arquitectura y componentes

- **Servicio:** `apps/services/login/`, mismo patrón de capas que
  `apps/services/library_soap_service` (`config/`, `db/`, `app.py`,
  `requirements.txt`, `.env`, `.env.example`, `README.md`).
- **Puerto:** 5000.
- **Rol de BD:** `auth_service_user`, mínimo privilegio, análogo a
  `soap_service_user`, con permisos solo sobre las tablas propias del
  microservicio (`cuentas`, `personas`, `codigos_verificacion`, `sesiones`)
  — ninguna tabla del monolito.
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
- **Monolito:** no se toca. Ni su código, ni su tabla `usuarios`, ni sus
  vistas/funciones. El microservicio tiene su propio registro de cuentas,
  separado del de la tienda — un usuario que ya existe en el monolito no
  existe automáticamente aquí, y viceversa (aceptado explícitamente para no
  invertir tiempo en normalizar una tabla ajena en producción).

## 3. Modelo de datos

Cuatro tablas nuevas, todas propias del microservicio, sin FK hacia
ninguna tabla del monolito:

```sql
-- Identidad/credenciales (propia del microservicio, NO es usuarios del monolito)
cuentas (
  id_cuenta        SERIAL PRIMARY KEY,
  correo           VARCHAR(150) NOT NULL UNIQUE,
  contrasena_hash  VARCHAR(255) NOT NULL,
  rol              VARCHAR(10)  NOT NULL DEFAULT 'cliente' CHECK (rol IN ('admin','cliente')),
  fecha_registro   TIMESTAMP    NOT NULL DEFAULT now()
)

-- Datos de persona, 1:1 con cuentas
personas (
  id_cuenta         INT PRIMARY KEY REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
  nombre            VARCHAR(100) NOT NULL,
  apellido_paterno  VARCHAR(100) NOT NULL,
  apellido_materno  VARCHAR(100) NOT NULL
)

-- Códigos 2FA pendientes
codigos_verificacion (
  id_codigo    SERIAL PRIMARY KEY,
  id_cuenta    INT NOT NULL REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
  codigo_hash  VARCHAR(255) NOT NULL,
  expira_en    TIMESTAMP NOT NULL,
  usado        BOOLEAN NOT NULL DEFAULT false,
  creado_en    TIMESTAMP NOT NULL DEFAULT now()
)

-- Sesiones activas
sesiones (
  token        VARCHAR(64) PRIMARY KEY,
  id_cuenta    INT NOT NULL REFERENCES cuentas(id_cuenta) ON DELETE CASCADE,
  creada_en    TIMESTAMP NOT NULL DEFAULT now(),
  expira_en    TIMESTAMP NOT NULL
)
```

Un solo script SQL aditivo (`CREATE TABLE`, sin `ALTER`/`DROP` sobre nada
existente) crea las 4 tablas y el rol `auth_service_user`. El campo
`id_usuario` que expone la API pública (sección 4) es el `id_cuenta`
interno, aliaseado en la capa de acceso a datos — el contrato HTTP no
cambia por este rediseño interno.

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

**Ninguno.** El monolito no se toca — ni su código, ni `usuarios`, ni sus
vistas/funciones/triggers. El microservicio de login tiene su propio
registro de cuentas (sección 3), completamente separado.

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
