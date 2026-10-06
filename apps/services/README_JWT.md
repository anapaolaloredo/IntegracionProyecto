# Microservicios con JWT

Seis servicios Flask independientes que comparten un mismo `SECRET_KEY` para firmar y validar
tokens JWT (módulo común en `apps/services/common`).

## Servicios y puertos

| Servicio  | Puerto | Función                                                                 |
|-----------|--------|-------------------------------------------------------------------------|
| `login`   | 5000   | Registro, login con 2FA, emisión de `session_token`/`refresh_token`, `/session/refresh` |
| `soap`    | 5001   | Servicio SOAP de libros (escrituras con JWT válido)                     |
| `users`   | 5002   | Usuarios con roles admin/cliente (`POST /api/users` solo admin)         |
| `authors` | 5003   | Autores y relación `libro_autor` (escritura solo admin)                 |
| `pedidos` | 5004   | Pedidos con stock transaccional y estados                               |
| `pagos`   | 5005   | Pagos; actualizan `pedidos.estado` en la misma transacción              |

## Variables de entorno (ver `.env.example` de cada servicio)

| Variable | Servicios | Notas |
|----------|-----------|-------|
| `SECRET_KEY` | todos | **Debe ser idéntica en los seis servicios**, si no los tokens se rechazan. |
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
cp .env.example .env               # y ajustar valores (mismo SECRET_KEY en todos)
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
  `AI_CHANGELOG`).
- **La prueba de humo de punta a punta contra una base de datos real NO se ejecutó** (ni Postfix/SMTP).
  La guía de curl anterior es solo documentación.
- Los cambios de UI del cliente de escritorio solo se comprobaron con `py_compile`, no se ejecutaron.
- Los GRANTs de la migración a `library_user` son amplios (DML completo sobre `cuentas`, incluida
  `contrasena_hash`, `autores`, `libro_autor`, y UPDATE sobre `libros`) porque todos los servicios
  comparten un solo rol de BD. Seguimiento recomendado: un rol por servicio con permisos mínimos.
- El logout JWT es sin estado: el token sigue siendo válido hasta que expira (el cliente solo lo descarta).
