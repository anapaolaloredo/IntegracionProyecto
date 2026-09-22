# App de escritorio (Python + PySide6) — Cliente de microservicios

Aplicacion grafica independiente que consume por HTTP el microservicio de
login (`apps/services/login`) y el de libros (`apps/services/soap`). Nunca
accede directamente a la base de datos.

## Requisitos

- Python 3.10 o superior
- Los dos microservicios accesibles por red (local o en la instancia de GCP)

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

Pruebas del nucleo (sin interfaz): `python -m pytest tests -q`

## Configuracion del servidor

Desde el login ("Configuracion del servidor…") o desde la pestana
"Configuracion del servidor" se pueden cambiar, probar, guardar y restaurar
las URLs. Se guardan fuera del codigo, en:

- macOS: `~/Library/Application Support/LibreriaEscritorio/config.json`
- Windows: `%APPDATA%\LibreriaEscritorio\config.json`

Para la instancia: `http://<IP_EXTERNA>:5000` (login) y `http://<IP_EXTERNA>:5001` (libros).

> En macOS el puerto 5000 local lo ocupa AirPlay Receiver (responde 403).
> Para correr login en local usa otro puerto (`PORT=5055 python app.py`) y
> configura esa URL en la app.

## Endpoints que usa

| Seccion | Metodo y ruta |
|---|---|
| Registro | `POST /register` |
| Inicio de sesion (2FA) | `POST /login` → codigo al buzon local de la instancia → `POST /login/verify` |
| Sesion | `GET /session`, `POST /session/extend`, `POST /logout` |
| Estado login | `GET /health` |
| Estado libros | `GET /api/libros/temas?isbn=__healthcheck__` (consulta ligera que toca la BD; el servicio no tiene `/health`) |
| Catalogo y busqueda | `GET /api/libros`, `GET /api/libros/buscar`, `GET /api/libros/{isbn}` |
| Administracion | `POST /api/libros`, `PUT /api/libros/{isbn}`, `DELETE /api/libros/{isbn}` |

El codigo 2FA llega al buzon del usuario configurado en `LOCAL_MAILBOX_USER`
dentro de la instancia: `sudo tail -20 /var/mail/<usuario>`.

## Estado de los servicios

- Verde: responde y tiene acceso a su base de datos.
- Amarillo: responde por HTTP pero con error (p. ej. 503 con la BD caida) o
  con una respuesta que no corresponde al servicio.
- Rojo: sin conexion, timeout o URL invalida.

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
