# Pruebas de estres con Locust (GUI en Windows 11)

`locustfile.py` prueba dos microservicios de la instancia de GCP con **20 usuarios simultaneos**:

| Clase | Servicio | URL base |
|---|---|---|
| `SoapUser` | Libros (XML) | `http://136.80.175.191:5001` |
| `UsersUser` | Usuarios (JSON) | `http://136.80.175.191:5002` |

Con 20 usuarios en total, Locust reparte 10 por clase (ambas tienen el mismo `weight`).

## Endpoints que se prueban

**Libros (5001)**

| Metodo | Ruta | Notas |
|---|---|---|
| GET | `/api/libros` | lista completa |
| GET | `/api/libros/catalogo` | datos minimos + imagenes |
| GET | `/api/libros/temas` | |
| GET | `/api/libros/buscar` | filtros `titulo`, `autor`, `genero`, `formato`, `anio`, `precio_min`, `precio_max` |
| GET | `/api/libros/<isbn>` | usa ISBN reales leidos del catalogo; tambien uno inexistente (espera 404) |
| GET | `/health`, `/metrics` | |
| POST / PUT / DELETE | `/api/libros`, `/api/libros/<isbn>` | solo con `LOCUST_TOKEN` de admin; crea, edita y borra un libro propio de la prueba |

**Usuarios (5002)**

| Metodo | Ruta | Notas |
|---|---|---|
| GET | `/` y `/?format=json` | el servicio no define `/`; el 404 se cuenta como respuesta esperada |
| GET | `/api/roles`, `/health`, `/metrics` | publicos |
| GET | `/api/users` sin token | espera 401 |
| GET | `/api/users`, `/api/users/<id>` | solo con `LOCUST_TOKEN` |

Sin `LOCUST_TOKEN` solo se ejecutan las rutas publicas. El login usa 2FA por buzon local de la instancia, por eso el
token no se obtiene dentro de Locust: inicia sesion con la app de escritorio o con `/login` + `/login/verify`
y copia el `session_token` (dura 30 minutos).

## Instalacion en Windows 11

1. Instala Python 3.10 o superior desde https://www.python.org/downloads/ (marca **Add python.exe to PATH**).
2. Abre PowerShell en esta carpeta (`apps\tests\locust`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell bloquea el script de activacion, ejecuta una vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Uso de la GUI

1. (Opcional) define el token y la IP **antes** de arrancar:

```powershell
$env:LOCUST_TOKEN = "pega_aqui_el_session_token"
$env:HOST_IP = "136.80.175.191"   # solo si la IP cambio
```

2. Arranca Locust:

```powershell
locust -f locustfile.py
```

3. Abre http://localhost:8089 en el navegador.
4. En el formulario **Start new load test** pon:
   - **Number of users:** `20`
   - **Ramp up:** `5` (usuarios que se agregan por segundo)
   - **Host:** deja el valor por defecto; cada clase ya trae su propio host.
   - (Opcional) en *Advanced options* pon **Run time** `2m`.
5. Pulsa **Start**. Revisa las pestanas:
   - **Statistics:** peticiones, fallos, tiempos medio/mediano y req/s por endpoint.
   - **Charts:** usuarios, req/s y tiempos de respuesta en el tiempo.
   - **Failures:** causa de cada fallo.
   - **Download Data:** CSV y reporte HTML para la evidencia.
6. Pulsa **Stop** para terminar. Para cerrar Locust, Ctrl+C en PowerShell.

## Modo sin GUI (opcional)

```powershell
locust -f locustfile.py --headless -u 20 -r 5 -t 2m --html reporte.html
```

## Resultado de referencia

Corrida de 20 s con 20 usuarios (sin token): 201 peticiones, 0 fallos, mediana 120 ms, 11 req/s.

> Ejecuta estas pruebas solo contra tu propia instancia. Si la reinicias, revisa que la IP externa
> (`gcloud compute instances list`) siga siendo la misma.
