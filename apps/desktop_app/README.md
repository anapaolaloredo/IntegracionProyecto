# App de escritorio (Python + PySide6) — Cliente de microservicios

Aplicacion grafica independiente que consume por HTTP el microservicio de
login (`apps/services/login`) y el de libros (`apps/services/soap`). Nunca
accede directamente a la base de datos.

## Requisitos

- Python 3.10 o superior
- Biblioteca grafica: **PySide6** (Qt 6) — se eligio por ser oficial de Qt,
  multiplataforma (Windows/macOS/Linux) y con licencia LGPL compatible con
  distribucion libre.
- Los dos microservicios accesibles por red (local o en la instancia de GCP)
- En Linux sin entorno grafico (servidor headless) hacen falta ademas las
  librerias de sistema que Qt necesita para importar `QtWidgets` incluso sin
  mostrar ventana: ver "Solucion de problemas frecuentes" mas abajo.

## Dependencias

Listadas en [`requirements.txt`](./requirements.txt):

```
PySide6>=6.7
requests>=2.31
```

`PySide6` trae consigo `shiboken6`, `PySide6_Essentials` y `PySide6_Addons`
como dependencias transitivas (se instalan solos con `pip install -r
requirements.txt`, no hace falta listarlos aparte).

## Instalacion y ejecucion

```bash
cd apps/desktop_app
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Pruebas del nucleo (sin interfaz): `python -m pytest tests -q`

## Estructura principal de la aplicacion

```
apps/desktop_app/
├── main.py                  # Punto de entrada: crea QApplication y lanza login/ventana principal
├── requirements.txt
├── core/                    # Logica sin interfaz (facil de probar con pytest)
│   ├── config.py            #   Configuracion persistente (URLs, timeouts) en config.json del usuario
│   ├── http.py              #   Cliente HTTP comun: URLs, timeout, errores de red -> ServiceError
│   ├── auth_api.py          #   Cliente del microservicio de login (register/login/2FA/sesion)
│   ├── books_api.py         #   Cliente del microservicio de libros (catalogo, busqueda, CRUD)
│   ├── health.py            #   Semaforo de estado (OK/DEGRADADO/CAIDO) de ambos microservicios
│   └── session_store.py     #   Recuerda localmente el ultimo token/correo (se revalida al abrir)
├── ui/                       # Interfaz grafica (PySide6), consume solo `core/`
│   ├── main_window.py        #   Ventana principal: pestanas + temporizadores de salud/expiracion
│   ├── login_window.py       #   Registro e inicio de sesion (2FA)
│   ├── catalog_tab.py        #   Catalogo remoto: lista, busqueda y detalle con imagenes
│   ├── admin_tab.py          #   Administracion de libros (crear/editar/eliminar)
│   ├── config_panel.py       #   Pantalla para editar/probar/guardar las URLs de los servicios
│   ├── async_task.py         #   Ejecuta llamadas HTTP fuera del hilo de UI (evita bloqueos)
│   └── common.py             #   Utilidades compartidas de UI (semaforo visual, mensajes de error)
└── tests/
    └── test_core.py          # Pruebas de `core/` sin necesidad de PySide6 ni servicios reales
```

Principio de diseño: `core/` no importa nada de PySide6 (se puede probar con
`pytest` sin interfaz grafica ni GUI toolkit); `ui/` solo llama a `core/` y
nunca abre conexiones HTTP ni de base de datos por su cuenta.

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

## Problemas conocidos

- El microservicio de libros no expone `GET /health`; el semaforo usa una
  consulta liviana (`GET /api/libros/temas?isbn=__healthcheck__`) como proxy,
  asi que un cambio en esa ruta especifica podria afectar la deteccion de
  estado aunque el resto del servicio siga funcionando.
- El 2FA depende de que el correo llegue al buzon local de la instancia
  (Postfix); en una maquina sin ese correo configurado, `POST /login` nunca
  completa el flujo (ver `apps/services/login/README_POSTFIX.md`).
- La app es de escritorio (GUI): en un servidor sin entorno grafico
  (headless) no se puede ver la ventana aunque el proceso corra sin errores,
  a menos que se use reenvio X11 (`ssh -X`) o un servidor VNC.

## Solucion de problemas frecuentes

**"No jala"/no conecta con los microservicios (catalogo o login vacios,
errores de conexion constantes)**
Revisa primero la URL configurada (pestana "Configuracion del servidor"):
`http://localhost:5000` solo funciona si la app corre en la *misma* maquina
donde vive el microservicio. Si la app corre en tu laptop y los servicios
estan en la instancia de GCP, usa la IP publica: `http://<IP_EXTERNA>:5000`
y `http://<IP_EXTERNA>:5001`.

**En macOS, el login siempre sale en amarillo/rojo aunque el servicio este
arriba**
El puerto 5000 local en macOS suele estar ocupado por "AirPlay Receiver"
(Centro de Control), que responde HTTP 403 en vez de dar connection
refused — la app lo detecta como "respuesta inesperada". Corre el
microservicio de login en otro puerto (`PORT=5055 python app.py` dentro de
`apps/services/login`) y actualiza la URL en la app, o desactiva AirPlay
Receiver en Configuracion del Sistema > General > AirDrop y Handoff.

**`ImportError: libGL.so.1` / `libEGL.so.1: cannot open shared object file`
al hacer `python main.py` en Linux**
Faltan librerias de sistema que Qt necesita para importar `QtWidgets`
(independientes de si hay pantalla o no). En distribuciones basadas en
RHEL/CentOS/Fedora:

```bash
sudo dnf install -y mesa-libGL mesa-libEGL mesa-libgbm libxkbcommon \
  libxkbcommon-x11 xcb-util-cursor xcb-util-wm xcb-util-keysyms \
  xcb-util-image xcb-util-renderutil
```

En Debian/Ubuntu el equivalente es `libgl1 libegl1 libxkbcommon-x11-0
libxcb-cursor0`. Si solo quieres confirmar que la app arranca sin crashear
(sin ver la ventana), fuerza el backend sin pantalla:
`QT_QPA_PLATFORM=offscreen python main.py`.

**El login funciona pero el catalogo/administracion da error de base de
datos, o el microservicio de libros regresa 500**
Eso ocurre del lado del microservicio, no de esta app: confirma que las
vistas/tablas de PostgreSQL existan y que el rol de la base tenga permisos
de `SELECT`/`INSERT` sobre ellas (`\dv`, `\dt`, `\du` en `psql`). No es algo
que la app de escritorio pueda arreglar por su cuenta.

**"El servicio respondio HTTP 403/404 con una respuesta inesperada"**
Casi siempre significa que la URL configurada apunta a otro programa (no al
microservicio esperado) — revisa el puerto y que el servicio correcto este
corriendo ahi.

**La sesion se cierra sola / "Tu sesion expiro"**
Las sesiones duran 30 minutos; la app avisa cuando faltan 5 o menos. Si
ocurre antes de tiempo, confirma que el reloj del servidor y el de tu
maquina no esten muy desincronizados.
