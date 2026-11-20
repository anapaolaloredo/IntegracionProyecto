# Evidencias del reverse proxy

Capturas de los tres clientes de escritorio apuntando al NGINX de `deploy/nginx/` (puerto 80),
tomadas en local con servicios simulados detrás del proxy.

| Archivo | Qué muestra |
|---|---|
| `electron_gateway.png` | Electron con URL base `http://127.0.0.1` (sin puerto): catálogo cargado por `/api/libros/catalogo`. |
| `pythontk_gateway.png` | PythonTk con la casilla de gateway: seis URLs derivadas de un host y los seis servicios en verde por `/health/<servicio>`. |
| `java_gateway.png` | Java con "El servidor usa el gateway NGINX": login a `POST /api/auth/login` aceptado (pide el código de 6 dígitos). |
| `animacion_gateway.png` · `animacion_balancer.png` | Animación didáctica (`docs/animacion_proxy/`). |
| `access_log_nginx.txt` | Peticiones registradas por NGINX, con el User-Agent de cada cliente. |
| `nginx_test.txt` | Resultado de `nginx -t` sobre los 3 archivos. |

Los datos del catálogo y las respuestas de login son de prueba (servicios simulados); no son de la instancia real.
