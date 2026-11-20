# Library · Cliente de escritorio (Java + JavaFX)

Cliente de escritorio de la librería. Consume por REST/JSON los microservicios de `apps/services` desplegados en GCP
(sin tocar PostgreSQL) y muestra el seguimiento de entregas en un mapa (Leaflet + OpenStreetMap en un `WebView`) alimentado
por un WebSocket.

```
App Java (JavaFX) ──REST + JWT──► login:5000  libros(soap):5001  users:5002  authors:5003  pedidos:5004  pagos:5005
        │
        └──WebSocket (JWT en el 1er mensaje)──► tracking_server:5006 (Flask + Flask-Sock) ──GET /api/pedidos/<id>──► pedidos
        └── WebView: Leaflet/OSM (el mapa solo dibuja lo que Java le entrega con executeScript)
```

## Requisitos
- JDK 21 y Maven 3.9 (`brew install maven openjdk@21`). JavaFX 21 se descarga como dependencia de Maven.
- Para el rastreo: Python 3.10+ en la instancia de GCP donde corren los servicios.

## Ejecutar el cliente
```bash
cd apps/JavaDesktop_app
JAVA_HOME=$(/usr/libexec/java_home -v 21) mvn javafx:run      # pruebas: mvn test
```
En el login se escribe la **IP o dominio** de la instancia (cambia en cada sesión; los puertos son fijos), el correo y la contraseña.

## Modo gateway (opcional)
Si en la instancia se instala el NGINX de `deploy/nginx/` (`./instalar_nginx.sh`), todo queda bajo el puerto 80 y en el login se marca
**"El servidor usa el gateway NGINX"**. Rutas: `/api/auth/*` (login), `/api/libros`, `/api/users`, `/api/authors`, `/api/pedidos`,
`/api/pagos` y `ws://<IP>:8090/ws/rastreo`. Sin marcar la casilla, la app usa un puerto por servicio como antes.

## Servidor de rastreo (en la instancia de GCP)
```bash
cd apps/JavaDesktop_app/tracking_server
python -m venv .venv && .venv/bin/pip install -r requirements.txt
PEDIDOS_URL=http://127.0.0.1:5004 .venv/bin/python app.py      # puerto 5006
```
Hay que abrir el puerto **5006/tcp** en el firewall de GCP (como los demás servicios). Variables: `PEDIDOS_URL`, `PORT`,
`SIM_DURACION_S` (duración total del recorrido, 120 s por omisión), `SIM_INTERVALO_S` (1 s). Pruebas: `.venv/bin/python -m pytest`.

## Cómo cumple cada módulo
| Módulo | Servicio real usado | Notas |
|---|---|---|
| 1 Login / Users | `POST /login`, `POST /login/verify`, `POST /session/refresh`, `POST /logout`, `GET /api/users/<id>` | Login sin modificar: 2 pasos (contraseña + código 2FA). El JWT va en `Authorization: Bearer`. Ante 401 intenta renovar con el refresh token; si falla, vuelve al login. |
| 2 Catálogo | `GET /api/libros`, `/api/libros/buscar?titulo=`, `/api/libros/<isbn>`, `GET /api/authors`, `/api/authors/<id>` | El catálogo responde XML; se lee con DOM (DTD deshabilitado). |
| 3 Cesta | (en memoria) + revalidación con `/api/libros/<isbn>` | Antes de comprar compara precio y stock vigentes y avisa de cambios. |
| 4 Compra | `POST /api/pedidos` → `POST /api/pagos` → `GET /api/pedidos/<id>` | Pago simulado: solo `id_pedido` + `metodo`. Si el pago falla, el pedido se cancela (devuelve stock). |
| 5 Mis compras | `GET /api/pedidos`, `GET /api/pagos` | "Pagado" se muestra solo si existe el pago real. |
| 6 Rastreo | WebSocket `/ws/rastreo` | Ver abajo. |

## Rastreo: decisiones de diseño
- **Código**: `LIB-MTY-<año>-<id_pedido a 6 dígitos>`, derivado del pedido real (no hay tabla nueva ni cambios a los servicios).
  El servidor comprueba que el año coincida con la fecha del pedido.
- **Autorización**: el servidor reenvía el JWT a `GET /api/pedidos/<id>`. Así reutiliza firma, expiración, revocación en Redis y la
  regla "el pedido es tuyo" (401/403/404) de `pedidos`, sin duplicar el secreto. Solo se rastrean pedidos `pagado` o `enviado`.
- **Ruta**: cada pedido recibe una de 5 rutas por calles reales de Monterrey (`data/rutas_monterrey.json`, generadas con OSRM);
  pedidos distintos pueden tener rutas distintas y el mismo pedido siempre la misma.
- **Estados**: confirmado → preparando → enviado (vehículo detenido en el origen) → en ruta (se mueve) → **Entregado solo al
  llegar al último punto**. Reconsultar el código continúa el mismo recorrido mientras el servidor siga encendido.

## Limitaciones conocidas
- No existe servicio "books" aparte: el catálogo viene del servicio de libros existente (`apps/services/soap`, XML).
- El catálogo no trae descripción; se arma con las definiciones de los conceptos del libro.
- El estado de entrega del simulador es independiente del estado del pedido (`pendiente/pagado/enviado/cancelado`): "Entregado"
  no modifica el pedido.
- El código 2FA llega al buzón local de la instancia (Postfix); hay que leerlo por SSH.
- El avance del simulador vive en memoria: si se reinicia `tracking_server`, el recorrido empieza de nuevo.
- Los mosaicos del mapa requieren internet (OpenStreetMap); Leaflet va incluido localmente.
- Las funciones de administración se limitan a lo que ya permiten los servicios (un admin ve todos los pedidos y puede marcar
  `pagado → enviado`).
- No se incluyó la integración SOAP demostrativa.
