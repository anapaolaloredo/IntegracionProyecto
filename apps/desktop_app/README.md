# App de escritorio (Python + PySide6) — Cliente de microservicios

Aplicacion grafica independiente que consume por HTTP los **seis microservicios**
(`apps/services`: login, libros/soap, users, authors, pedidos y pagos) con
formularios CRUD, semaforos de estado (incluido Redis) y un radio http/https.
Nunca accede directamente a la base de datos.

## Requisitos

- Python 3.10 o superior
- Los seis microservicios accesibles por red (local, en la instancia de GCP o por tunel SSH)

## Instalacion y ejecucion

```bash
cd apps/desktop_app
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> **macOS con iCloud ("Escritorio y Documentos")**: si el proyecto esta en
> `~/Documents`, crea el venv FUERA de esa carpeta. iCloud deja las carpetas
> de plugins de Qt en un estado que Qt no puede listar y la app falla con
> `Could not find the Qt platform plugin "cocoa"`:
>
> ```bash
> python3 -m venv ~/.venvs/libreria-escritorio
> ~/.venvs/libreria-escritorio/bin/pip install -r requirements.txt
> ~/.venvs/libreria-escritorio/bin/python main.py
> ```

Pruebas (nucleo y pestanas, sin red): `pip install pytest && QT_QPA_PLATFORM=offscreen python -m pytest tests -q`

## Configuracion del servidor

Desde el login ("Configuracion del servidor…") o desde la pestana
"Configuracion del servidor" se pueden cambiar, probar, guardar y restaurar
las **seis URLs** y los tiempos. Se guardan fuera del codigo, en:

- macOS: `~/Library/Application Support/LibreriaEscritorio/config.json`
- Windows: `%APPDATA%\LibreriaEscritorio\config.json`

Puertos: login `5000`, libros `5001`, users `5002`, authors `5003`, pedidos `5004`, pagos `5005`.
Para la instancia: `http://<IP_EXTERNA>:<puerto>`.

**Protocolo (radio http / https).** Por defecto `http`. Al elegir `https` se reescribe
el esquema de las seis URLs (host y puerto no cambian); al volver a `http` se
regresan. `https` solo funciona cuando el servidor (o un proxy) tiene certificado.
Una URL editada a mano manda sobre el radio.

**Sin abrir los puertos en el firewall de GCP**: usa un tunel SSH y deja las URLs en `localhost`:

```bash
ssh -N -L 5000:localhost:5000 -L 5001:localhost:5001 -L 5002:localhost:5002 \
       -L 5003:localhost:5003 -L 5004:localhost:5004 -L 5005:localhost:5005 usuario@IP_EXTERNA
```

> En macOS el puerto 5000 local lo ocupa AirPlay Receiver (responde 403). Con el
> tunel, usa otro puerto local para login (`-L 5055:localhost:5000`) y configura
> `http://localhost:5055`.

## Pestanas, servicios y endpoints

| Pestana | Servicio | Endpoints | Quien |
|---|---|---|---|
| Catalogo de libros | libros :5001 | `GET /api/libros`, `/buscar`, `/{isbn}` | publico |
| Administracion de libros | libros :5001 | `POST`, `PUT`, `DELETE /api/libros` | POST/DELETE admin; PUT cualquier sesion |
| Usuarios | users :5002 | `GET/POST /api/users`, `PATCH /api/users/{id}`, `/password`, `/rol`, `DELETE` | admin: todos; cliente: solo su cuenta (editar y cambiar su contrasena) |
| Autores | authors :5003 | `GET /api/authors[/{id}]` (publico); `POST/PATCH/DELETE`, `POST/DELETE /{id}/books` | escritura solo admin |
| Pedidos | pedidos :5004 | `POST/GET /api/pedidos`, `GET /{id}`, `PATCH /{id}/estado`, `DELETE /{id}` | cliente: los suyos (crear, cancelar); admin: todos, enviar y eliminar |
| Pagos | pagos :5005 | `POST/GET /api/pagos`, `GET /{id}`, `DELETE /{id}` | cliente: pagar lo suyo; admin: ver todos y reembolsar |
| Sesion y perfil | login :5000 | `GET /session`, `POST /session/extend`, `/session/refresh`, `POST /logout` | sesion |
| Registro / inicio (2FA) | login :5000 | `POST /register`, `POST /login` → codigo al buzon local → `POST /login/verify` | publico |
| Estado de los servicios | los seis | `GET /health` | publico |

Los botones solo-admin se deshabilitan (con tooltip) para un cliente; si aun asi el
servidor responde 403 o 409 (p. ej. stock insuficiente), se muestra su mensaje tal cual.
Un 503 (Redis caido) **no** cierra la sesion: la app avisa y reintenta.

El codigo 2FA llega al buzon del usuario configurado en `LOCAL_MAILBOX_USER`
dentro de la instancia: `mail` (o `sudo tail -20 /var/mail/<usuario>`).

## Estado de los servicios

Cada servicio se comprueba con `GET /health` (`{"db": ..., "redis": ...}`).

- Verde: responde y tiene acceso a su base de datos.
- Amarillo: responde por HTTP pero con error (p. ej. 503 con la BD caida) o
  con una respuesta que no corresponde al servicio.
- Rojo: sin conexion, timeout o URL invalida.

El estado de **Redis** se muestra aparte en cada tarjeta y en un resumen "Redis
compartido"; no cambia el color del servicio (las lecturas publicas funcionan sin Redis).

Se comprueba al abrir, con el boton "Comprobar ahora" y automaticamente cada
N segundos (configurable). Se muestra la fecha y hora de la ultima comprobacion.

## Prueba de tolerancia a fallos (resultados en local)

| Caso | Que se hizo | Como reacciono la app |
|---|---|---|
| A | Ambos servicios arriba | Login y Libros en verde, catalogo con 30 libros, CRUD completo correcto |
| B | Libros apuntando a un puerto sin servicio (equivale a detenerlo) | Libros en rojo en la siguiente comprobacion; el catalogo muestra "No se pudo conectar con el servicio de Libros en …"; login sigue en verde; la app no se cierra |
| C | Libros restaurado | Vuelve a verde y el catalogo se recarga |
| D | URL sin `http://` / puerto de otro programa (5000 = AirPlay) | La URL mal escrita se rechaza al guardar; el puerto ajeno aparece en amarillo: "Respondio HTTP 403 con una respuesta inesperada" |

Tambien se verificaron: credenciales incorrectas (401), ISBN duplicado (409),
libro inexistente (404), sesion eliminada en el servidor (regresa al login con
aviso) y aviso de expiracion cuando faltan 5 minutos o menos.

## Checklist manual para las evidencias (con los servicios en la GCP)

1. **Semaforos:** pestana "Estado de los servicios": seis tarjetas en verde y "Redis compartido: funcionando".
2. **Servicio caido:** detener uno (`pkill -f "authors/app.py"` o el proceso que corresponda) → su tarjeta y su mini-semaforo pasan a rojo; volver a levantarlo → verde.
3. **Admin:** iniciar sesion (2FA) y hacer el CRUD completo: crear/editar/cambiar rol/eliminar usuario; crear/renombrar/vincular libro/eliminar autor; crear pedido con dos lineas; pagar; reembolsar; cancelar; crear/actualizar/eliminar libro.
4. **Cliente:** registrarse e iniciar sesion: botones de admin deshabilitados; ve solo sus pedidos y pagos; solo su usuario.
5. **Errores del servidor:** pedido con cantidad 9999 → 409 "Stock insuficiente"; pagar un pedido ya pagado → 409.
6. **Cerrar sesion:** las pestanas Usuarios, Pedidos y Pagos piden iniciar sesion; Autores y Catalogo siguen publicos.
7. **Radio https:** en Configuracion elegir https → las seis URLs cambian de esquema; volver a http.
8. **Redis detenido** (`sudo systemctl stop redis`): "Redis compartido" en amarillo; las pestanas protegidas muestran el 503 del servidor y la sesion NO se cierra; el catalogo y los autores siguen funcionando. Volver a iniciar Redis.
9. Capturas: cada pestana y el **registro de peticiones HTTP** de la parte inferior (muestra metodo, URL, cuerpo y status; las contrasenas salen como `********`).
