# Revisión de seguridad — Librería en línea (Ejercicio Guiado 02)

Para cada control: **amenaza** que mitiga, **control aplicado** (verificado en el código o la
infraestructura) y **evidencia de prueba**. Los controles marcados como *Pendiente* no están
implementados todavía; se documentan igual porque forman parte del análisis de riesgo.

## 1. Controles mínimos requeridos por el ejercicio

| # | Amenaza | Control aplicado | Evidencia de prueba |
|---|---|---|---|
| 1 | Contraseñas comprometidas si se filtra la base de datos | Hash con `bcrypt` (10 rondas) en el registro; nunca se guarda texto plano | `authController.js`, `bcrypt.hash(contrasena, RONDAS_SAL)`; columna `contrasena_hash` en `usuarios` |
| 1b | Contraseñas triviales/débiles | Política **básica**: longitud mínima de 6 caracteres y confirmación de contraseña en el registro | `authController.registrar`: `if (contrasena.length < 6) throw ...` — **sin** requisito de mayúsculas/números/símbolos; considerar reforzarla |
| 2 | Exposición de credenciales en el código fuente | Secretos (`PGPASSWORD`, `SESSION_SECRET`, `BASE_PATH`) sólo en `.env`, cargado con `dotenv`; `.env` no versionado | `config/db.js`, `app.js` leen `process.env.*`; `.gitignore` excluye `.env` (verificar que también se excluya del `.tar.gz` de entrega) |
| 3 | SQL Injection | Todo acceso a datos vía funciones PL/pgSQL invocadas con parámetros posicionales (`$1, $2, ...`) desde `pg`; ninguna concatenación de strings con datos del usuario | Inspección de `models/*.js`: cero ocurrencias de template strings o `+` construyendo SQL con variables |
| 4 | Datos inválidos o maliciosos en formularios | Validación server-side en cada controlador (campos obligatorios, longitud mínima, coincidencia de contraseñas, existencia de FK antes de asociar) además de restricciones `CHECK` en PostgreSQL | `authController.registrar`, `libroController.crear`, `catalogoController.crear`; `CHECK (precio >= 0)`, `CHECK (stock >= 0)` en `data/library_schema.sql` |
| 5 | Escalación de privilegios / acceso a funciones administrativas por un usuario no-admin | Middleware `requerirAdmin` en **todas** las rutas de escritura de libros, catálogos y en **todo** el router de usuarios | Auditoría línea por línea documentada en `docs/ENGINEERING_DECISIONS.md` (D-09): no se encontró ninguna ruta administrativa sin protección al 31/08/2026 |
| 6 | Secuestro/fijación de sesión, sesión persistente tras logout | `express-session` + `connect-pg-simple` (sesión en servidor, no en el cliente); `req.session.destroy()` en logout; cookie con `maxAge` de 8 horas y `path` ajustado al prefijo de despliegue | `authController.cerrarSesion`; `app.js`, configuración de `session({...})` |
| 7 | Subida de archivos peligrosos (ejecutables, scripts, archivos sobredimensionados) | `multer` con `fileFilter` (whitelist de extensión + MIME: jpg/jpeg/png/webp/gif), límite de 5 MB, nombre de archivo generado por el sistema (nunca el original del usuario) | `middlewares/upload.js`; `libroController.subirImagen`: `urlPublica = /uploads/${req.file.filename}` |
| 8 | Fuga de información interna (stack traces, rutas del servidor, consultas SQL) al usuario final | Vista `error.ejs` genérica; en producción (`NODE_ENV=production`) el manejador de errores de `app.js` no expone `err.message` | `app.js`, manejador de errores de 4 argumentos: `mensaje: process.env.NODE_ENV === 'production' ? '...' : err.message` |
| 9 | Uso de un superusuario de PostgreSQL para correr la aplicación | *Pendiente de confirmar/documentar.* La app se conecta como `library_user` (no `postgres`), pero no hay evidencia guardada de los `GRANT`/`CREATE ROLE` que limitan explícitamente sus privilegios | **Pendiente:** ejecutar `\du` en `psql` y documentar aquí los privilegios exactos de `library_user` |
| 10 | Publicación accidental de secretos en `ubiquitous.udem.edu` | Checklist manual antes de publicar: excluir `.env`, `node_modules`, llaves SSH, tokens; publicar `.env.example` con nombres de variable sin valores | **Pendiente de ejecutar** al momento de armar `descargas/ejercicio02.tar.gz` — ver `html/ejercicio02/descargas/LEEME.txt` |

## 2. Riesgos adicionales identificados (no listados explícitamente por el ejercicio, pero relevantes)

| # | Amenaza | Estado actual | Notas |
|---|---|---|---|
| 11 | CSRF (Cross-Site Request Forgery) sobre los formularios `POST`/`PUT`/`DELETE` | **Sin mitigación explícita.** No hay token CSRF (no se usa `csurf` ni equivalente) y la cookie de sesión no fija `sameSite` explícitamente (queda en el default del navegador, típicamente `Lax`) | `Lax` bloquea CSRF disparado desde una navegación cross-site simple, pero **no** protege contra un formulario auto-enviado desde otro sitio que apunte al mismo dominio en una pestaña donde la víctima ya tiene sesión iniciada. Riesgo residual real, sobre todo en rutas de escritura del Administrador. |
| 12 | Fuerza bruta sobre login | **Sin mitigación.** No hay `express-rate-limit` ni bloqueo tras intentos fallidos | Un atacante puede probar contraseñas sin límite de intentos contra `/library/auth/login`. |
| 13 | Cabeceras de seguridad HTTP (X-Frame-Options, CSP, X-Content-Type-Options, etc.) | **Sin mitigación.** No está instalado `helmet` ni configuración manual de cabeceras | Expone a clickjacking y reduce las defensas de defensa-en-profundidad del navegador. |
| 14 | Puerto 3000 de Node expuesto a `0.0.0.0/0` en el firewall de GCP | Node sólo escucha en `127.0.0.1:3000` (no alcanzable aunque la regla exista), pero la regla de firewall `web-monolito01` permite el puerto 3000 desde cualquier IP | Ver `docs/GCP_COMMANDS.md`, sección 5: la regla debería eliminarse una vez confirmado que el reverse proxy funciona, dejando sólo el puerto público (80/443) abierto. |
| 15 | Enumeración de usuarios vía mensajes de error de login | Los mensajes de `iniciarSesion` usan siempre "Credenciales inválidas" para correo inexistente o contraseña incorrecta (no distinguen el caso) | Correcto — mitigación ya presente; se documenta como control positivo. |
| 16 | Falta de trazabilidad sobre quién obtiene o pierde el rol de Administrador | **Corregido (2026-08-31).** Trigger `trg_usuarios_auditoria_rol` registra en `usuarios_auditoria_rol` cada cambio de `rol` (anterior, nuevo, fecha), sin depender de que la aplicación lo registre manualmente | Verificado en `docs/TEST_PLAN.md` TC-24: 2 cambios de rol reales quedaron registrados con su fecha exacta. |

## 3. Resumen de estado

- **Controles verificados y correctos:** hash de contraseñas, SQL parametrizado, autorización por
  rol (auditoría completa), manejo de sesiones, validación de archivos, mensajes de error
  controlados, no distinguir usuario inexistente vs. contraseña incorrecta, bitácora de cambios
  de rol de Administrador (trigger, control #16).
- **Controles presentes pero débiles:** política de contraseñas (sólo longitud mínima).
- **Pendientes de confirmar con evidencia real:** privilegios exactos de `library_user` en
  PostgreSQL, checklist de publicación sin secretos.
- **Riesgos residuales aceptados para el alcance del ejercicio, a documentar como limitación
  conocida en el reporte técnico:** ausencia de protección CSRF explícita, sin límite de intentos
  de login, sin cabeceras de seguridad HTTP, regla de firewall del puerto 3000 más permisiva de lo
  necesario.
