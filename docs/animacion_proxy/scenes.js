/* Datos de las escenas: nodos, escenarios paso a paso, configuracion y conceptos.
   Convenciones:
     T(origen, destino, etiqueta, tipo, explicacion, extra)  -> un paquete que viaja
     K(nodo, burbuja, explicacion, extra)                    -> una decision interna (sin viaje)
   extra: { h: [lineas del paquete], hl: [texto de lineas de config a resaltar], pre/post: fn(stage) } */
(function () {
  'use strict';

  const N = (id, label, sub, x, y, o = {}) => ({ id, label, sub, x, y, w: o.w || 156, h: o.h || 46, icon: o.icon || '', kind: o.kind || 'server' });
  const T = (from, to, label, kind, text, extra = {}) => ({ from, to, label, kind, text, ...extra });
  const K = (at, bubble, text, extra = {}) => ({ at, bubble, text, kind: extra.kind || 'ctl', ...extra });

  /* ===================================================================== */
  /* 1. FORWARD PROXY                                                      */
  /* ===================================================================== */
  const forward = {
    id: 'forward', tab: 'Proxy directo (forward)', cmp: 0,
    title: 'Proxy directo (forward proxy)',
    summary: 'Está del lado del CLIENTE. Los equipos de una red salen a Internet a través de él. El cliente sabe que existe y lo configura; el servidor de destino solo ve la IP del proxy.',
    tags: ['Capa 7 (HTTP) / túnel CONNECT', 'Squid · Privoxy · Zscaler', 'Filtra, cachea y oculta al cliente'],
    nodes: [
      N('a', 'Laptop A', '10.0.0.5', 120, 110, { icon: '💻', kind: 'client' }),
      N('b', 'PC B', '10.0.0.6', 120, 340, { icon: '🖥️', kind: 'client' }),
      N('p', 'Forward Proxy', 'Squid :3128', 470, 225, { icon: '🛡️', kind: 'proxy', w: 176 }),
      N('net', 'ejemplo.com', '203.0.113.50', 850, 110, { icon: '🌐' }),
      N('bad', 'apuestas.com', 'lista negra', 850, 340, { icon: '🚫', kind: 'danger' }),
    ],
    links: [['a', 'p'], ['b', 'p'], ['p', 'net'], ['p', 'bad']],
    codeTitle: 'squid.conf (ejemplo, no está en el proyecto)',
    code: [
      '# Puerto donde escucha el proxy; los clientes lo configuran en su navegador',
      'http_port 3128',
      '',
      '# ACL: quién puede usarlo y qué dominios se bloquean',
      'acl red_interna src 10.0.0.0/24',
      'acl bloqueados dstdomain .apuestas.com',
      'acl SSL_ports port 443',
      'acl CONNECT method CONNECT',
      '',
      'http_access deny bloqueados',
      'http_access allow red_interna',
      'http_access deny all',
      '',
      '# Caché en disco: 100 MB',
      'cache_dir ufs /var/spool/squid 100 16 256',
      '',
      '# Anonimato: no revelar al sitio quién está detrás',
      'via off',
      'forwarded_for delete',
    ],
    concepts: [
      { t: 'El cliente lo conoce', d: 'Hay que configurarlo (navegador, variable HTTP_PROXY o PAC). Por eso la petición llega con URL absoluta: GET http://sitio/ruta.' },
      { t: 'Oculta al cliente', d: 'El servidor ve la IP del proxy. Es la base de la salida a Internet compartida y del anonimato básico.' },
      { t: 'Control de acceso (ACL)', d: 'Permite o bloquea por IP origen, dominio, puerto, horario o usuario (Proxy-Authorization).' },
      { t: 'Caché compartida', d: 'Si un compañero ya pidió el objeto y sigue vigente (TTL), se responde desde el proxy: HIT.' },
      { t: 'HTTPS con CONNECT', d: 'El proxy abre un túnel TCP y copia bytes cifrados. No ve URL ni contenido, salvo que se instale su CA (SSL bump).' },
      { t: 'Auditoría', d: 'Todo el tráfico saliente queda registrado en un solo punto (access.log).' },
    ],
    scenarios: [
      {
        name: 'Petición permitida (MISS)', build: () => ({
          steps: [
            T('a', 'p', 'GET http://ejemplo.com/logo.png', 'req', 'El navegador está configurado para usar el proxy, así que manda la petición COMPLETA (URL absoluta) al proxy y no al sitio. El cliente SABE que hay un proxy.', { h: ['GET http://ejemplo.com/logo.png HTTP/1.1', 'Host: ejemplo.com', 'Proxy-Authorization: Basic YW5hOioqKg==', 'User-Agent: Mozilla/5.0'], hl: ['http_port'] }),
            K('p', 'ACL ✔ red_interna\ncaché: MISS', 'El proxy evalúa sus reglas en orden: ¿la IP origen está permitida? ¿el dominio está bloqueado? ¿tiene el objeto en caché? Aquí: permitido y NO está en caché (MISS).', { hl: ['acl red_interna', 'http_access allow'] }),
            T('p', 'net', 'GET /logo.png', 'req', 'El proxy abre SU PROPIA conexión al sitio. El sitio ve la IP del proxy (203.0.113.9), no la de Laptop A: el proxy oculta al cliente.', { h: ['GET /logo.png HTTP/1.1', 'Host: ejemplo.com', 'IP origen TCP: 203.0.113.9 (la del proxy)', '(Via y X-Forwarded-For eliminados por "via off" / "forwarded_for delete")'], hl: ['via off', 'forwarded_for'] }),
            T('net', 'p', '200 OK · 48 KB', 'res', 'El sitio responde al proxy, que es quien le preguntó.', { h: ['HTTP/1.1 200 OK', 'Content-Type: image/png', 'Cache-Control: max-age=3600', 'Content-Length: 48211'] }),
            K('p', 'guarda en caché\nTTL 3600 s', 'Cache-Control: max-age=3600 autoriza guardar el objeto una hora. Se escribe en cache_dir.', { post: s => s.badge('p', 'caché: logo.png (1 h)', 'ok'), hl: ['cache_dir'] }),
            T('p', 'a', '200 OK', 'res', 'El proxy entrega el contenido a Laptop A. Para el cliente fue una respuesta normal.', { h: ['HTTP/1.1 200 OK', 'X-Cache: MISS from squid', 'Age: 0'] }),
          ],
        }),
      },
      {
        name: 'Segunda petición (HIT en caché)', build: () => ({
          setup: s => s.badge('p', 'caché: logo.png (1 h)', 'ok'),
          steps: [
            T('b', 'p', 'GET http://ejemplo.com/logo.png', 'req', 'Otro equipo de la red pide el MISMO objeto minutos después.', { h: ['GET http://ejemplo.com/logo.png HTTP/1.1', 'Host: ejemplo.com'] }),
            K('p', 'HIT ✔ (edad 12 s < TTL 3600 s)', 'El proxy encuentra el objeto vigente en su caché. No necesita ir a Internet.', { kind: 'res', hl: ['cache_dir'] }),
            T('p', 'b', '200 OK · X-Cache: HIT', 'res', 'Respuesta inmediata desde el proxy: cero bytes salieron a Internet. Ahorra ancho de banda y baja la latencia para todos.', { h: ['HTTP/1.1 200 OK', 'X-Cache: HIT from squid', 'Age: 12'], post: s => s.badge('p', 'caché: logo.png · hits: 1', 'ok') }),
          ],
        }),
      },
      {
        name: 'Sitio bloqueado (ACL)', build: () => ({
          steps: [
            T('a', 'p', 'GET http://apuestas.com/', 'req', 'Laptop A intenta entrar a un sitio prohibido por política.', { h: ['GET http://apuestas.com/ HTTP/1.1', 'Host: apuestas.com'] }),
            K('p', 'ACL ✘ dstdomain .apuestas.com\n→ http_access deny', 'La primera regla que coincide manda: el dominio está en la lista negra, así que se niega aunque la IP origen sí esté permitida. El orden de las reglas importa.', { kind: 'err', hl: ['http_access deny bloqueados', 'acl bloqueados'], post: s => s.fx('p', 'err') }),
            T('p', 'a', '403 Forbidden', 'err', 'El proxy devuelve una página de error propia (ERR_ACCESS_DENIED). El sitio bloqueado nunca fue contactado.', { h: ['HTTP/1.1 403 Forbidden', 'X-Squid-Error: ERR_ACCESS_DENIED 0', 'Content-Type: text/html'] }),
          ],
        }),
      },
      {
        name: 'HTTPS: túnel CONNECT', build: () => ({
          steps: [
            T('a', 'p', 'CONNECT ejemplo.com:443', 'req', 'Para HTTPS el navegador no manda la URL: pide un TÚNEL con el método CONNECT, indicando solo host y puerto.', { h: ['CONNECT ejemplo.com:443 HTTP/1.1', 'Host: ejemplo.com:443', 'Proxy-Authorization: Basic YW5hOioqKg=='], hl: ['acl CONNECT'] }),
            K('p', 'ACL: CONNECT solo a puerto 443 ✔', 'Squid solo permite CONNECT a los puertos de SSL_ports; si no, cualquiera podría usarlo para tunelizar cualquier cosa.', { hl: ['SSL_ports'] }),
            T('p', 'net', 'TCP SYN :443', 'tcp', 'El proxy abre un socket TCP hacia el destino (three-way handshake).'),
            T('net', 'p', 'SYN-ACK', 'tcp', 'El destino acepta la conexión.'),
            T('p', 'a', '200 Connection established', 'res', 'El proxy avisa que el túnel está listo. Desde aquí solo copia bytes en ambos sentidos.', { h: ['HTTP/1.1 200 Connection established', 'Proxy-Agent: squid'] }),
            T('a', 'p', '🔒 TLS ClientHello', 'tcp', 'El cliente negocia TLS DIRECTAMENTE con el sitio, usando el túnel. El proxy ya no entiende HTTP aquí.', { h: ['bytes TLS opacos para el proxy', '(SNI ejemplo.com viaja en claro en el ClientHello)'] }),
            T('p', 'net', '🔒 bytes cifrados', 'tcp', 'El proxy los reenvía sin descifrar. Solo podría inspeccionarlos si se instala su certificado raíz en los clientes (SSL bump).'),
            T('net', 'p', '🔒 ServerHello + certificado', 'tcp', 'El sitio responde con su certificado real.'),
            T('p', 'a', '🔒 bytes cifrados', 'tcp', 'Handshake completo y cifrado extremo a extremo. El proxy solo ve cuántos bytes pasan y hacia dónde.'),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* 2. REVERSE PROXY                                                      */
  /* ===================================================================== */
  const reverse = {
    id: 'reverse', tab: 'Proxy inverso (reverse)', cmp: 1,
    title: 'Proxy inverso (reverse proxy)',
    summary: 'Está del lado del SERVIDOR. El cliente cree que habla con el sitio, pero habla con NGINX, que reenvía a la aplicación interna. Oculta los servidores, termina TLS, comprime, cachea y protege.',
    tags: ['Capa 7 (HTTP)', 'NGINX · HAProxy · Traefik · Caddy', 'conf.d/01_reverse_proxy.conf'],
    nodes: [
      N('c', 'Cliente', 'Internet · 34.10.20.30', 120, 225, { icon: '🌐', kind: 'client' }),
      N('n', 'NGINX', ':80 (público)', 480, 225, { icon: '🛡️', kind: 'proxy', w: 170 }),
      N('app', 'Monolito Node', '127.0.0.1:3000 (privado)', 850, 225, { icon: '🖥️', w: 176 }),
    ],
    links: [['c', 'n'], ['n', 'app']],
    codeTitle: 'conf.d/01_reverse_proxy.conf',
    code: [
      'server {',
      '    listen 80 default_server;',
      '    server_tokens off;            # no revela la version de NGINX',
      '    client_max_body_size 10m;     # multer sube imagenes de libros',
      '',
      '    proxy_http_version 1.1;',
      '    proxy_set_header Host              $host;',
      '    proxy_set_header X-Real-IP         $remote_addr;',
      '    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;',
      '    proxy_set_header X-Forwarded-Proto $scheme;',
      '    proxy_connect_timeout 5s;',
      '    proxy_read_timeout    60s;',
      '',
      '    location = / { return 302 /library/; }',
      '    location /   { proxy_pass http://127.0.0.1:3000; }',
      '}',
    ],
    concepts: [
      { t: 'El cliente no lo sabe', d: 'No configura nada: resuelve el dominio y llega a NGINX. No ve que existe una app en 127.0.0.1:3000.' },
      { t: 'Oculta la infraestructura', d: 'Puertos, IPs y tecnología internos quedan fuera de Internet. Solo el 80 (o 443) está expuesto.' },
      { t: 'Cabeceras X-Forwarded-*', d: 'La app solo ve la IP de NGINX; con X-Real-IP / X-Forwarded-For / X-Forwarded-Proto recupera IP, cadena de proxies y esquema original.' },
      { t: 'Terminación TLS', d: 'NGINX descifra HTTPS y habla HTTP plano con la app en la red privada. Un solo certificado para todo.' },
      { t: 'Protección', d: 'client_max_body_size, timeouts, limit_req y server_tokens off frenan abusos antes de que toquen la app.' },
      { t: 'Errores del upstream', d: '502 si no conecta, 504 si tarda más que proxy_read_timeout. La app caída no tumba a NGINX.' },
    ],
    scenarios: [
      {
        name: 'GET / → 302 → /library/', build: () => ({
          steps: [
            T('c', 'n', 'GET /', 'req', 'El usuario entra a la raíz del dominio.', { h: ['GET / HTTP/1.1', 'Host: 34.10.20.30', 'Accept: text/html'], hl: ['location = /'] }),
            K('n', 'location = / → return 302', 'NGINX elige el location con coincidencia EXACTA (=). Responde él mismo: la app ni se entera.', { hl: ['location = /'] }),
            T('n', 'c', '302 → /library/', 'res', 'Redirección: el monolito vive bajo el prefijo /library (BASE_PATH).', { h: ['HTTP/1.1 302 Moved Temporarily', 'Location: http://34.10.20.30/library/', 'Server: nginx   ← sin versión por server_tokens off'], hl: ['server_tokens'] }),
            T('c', 'n', 'GET /library/', 'req', 'El navegador sigue la redirección.', { h: ['GET /library/ HTTP/1.1', 'Host: 34.10.20.30'] }),
            K('n', 'location / → proxy_pass :3000\n+ cabeceras X-Forwarded-*', 'No hay coincidencia exacta; entra el location / (prefijo). proxy_pass sin barra final conserva la URI completa: /library/ llega igual a Node.', { hl: ['location /   {', 'proxy_set_header'] }),
            T('n', 'app', 'GET /library/', 'req', 'NGINX abre una conexión HTTP/1.1 a la app y AÑADE cabeceras para que la app sepa quién es el cliente real.', { h: ['GET /library/ HTTP/1.1', 'Host: 34.10.20.30', 'X-Real-IP: 201.141.8.77', 'X-Forwarded-For: 201.141.8.77', 'X-Forwarded-Proto: http', 'IP origen TCP: 127.0.0.1  (la de NGINX)'], hl: ['X-Real-IP', 'X-Forwarded-For', 'X-Forwarded-Proto'] }),
            T('app', 'n', '200 OK · HTML', 'res', 'La app responde a NGINX, nunca directamente al cliente.', { h: ['HTTP/1.1 200 OK', 'Content-Type: text/html; charset=utf-8', 'X-Powered-By: Express'] }),
            T('n', 'c', '200 OK · HTML', 'res', 'NGINX reenvía la respuesta. El cliente nunca vio 127.0.0.1:3000.', { h: ['HTTP/1.1 200 OK', 'Server: nginx'] }),
          ],
        }),
      },
      {
        name: 'Terminación TLS (https)', build: () => ({
          steps: [
            T('c', 'n', '🔒 TLS ClientHello :443', 'tcp', 'Con HTTPS, el cliente negocia TLS con NGINX, no con la app. (El proyecto hoy solo publica :80; con un certificado se añadiría listen 443 ssl.)', { h: ['ClientHello · SNI: tienda.ejemplo.com', 'Cifrados: TLS_AES_256_GCM_SHA384…'] }),
            T('n', 'c', '🔒 certificado + ServerHello', 'tcp', 'NGINX presenta el certificado del dominio. Solo se instala UNA vez, en el proxy.'),
            K('n', 'descifra la petición\nHTTPS → HTTP', 'Con la sesión TLS establecida, NGINX lee la petición en claro y puede aplicar reglas, límites y cachés.', { kind: 'tcp' }),
            T('c', 'n', '🔒 GET /library/ (cifrado)', 'tcp', 'La petición viaja cifrada por Internet.'),
            T('n', 'app', 'GET /library/ (HTTP plano)', 'req', 'En la red privada la app recibe HTTP normal. X-Forwarded-Proto: https le indica que el cliente SÍ usó TLS (para generar enlaces https y cookies Secure).', { h: ['GET /library/ HTTP/1.1', 'X-Forwarded-Proto: https', 'X-Forwarded-For: 201.141.8.77'], hl: ['X-Forwarded-Proto'] }),
            T('app', 'n', '200 OK', 'res', 'Respuesta en claro dentro de la red privada.'),
            T('n', 'c', '🔒 200 OK (cifrado)', 'tcp', 'NGINX la cifra otra vez hacia el cliente.'),
          ],
        }),
      },
      {
        name: 'Subida grande (413)', build: () => ({
          steps: [
            T('c', 'n', 'POST /library/libros · 3 MB', 'req', 'Subida de una imagen de portada (multipart/form-data).', { h: ['POST /library/libros HTTP/1.1', 'Content-Type: multipart/form-data; boundary=----x', 'Content-Length: 3145728'], hl: ['client_max_body_size'] }),
            K('n', '3 MB ≤ 10 MB ✔', 'NGINX compara Content-Length con client_max_body_size (10m). Pasa.', { kind: 'res', hl: ['client_max_body_size'] }),
            T('n', 'app', 'POST /library/libros', 'req', 'Reenvía el cuerpo a la app.'),
            T('app', 'n', '201 Created', 'res', 'La app guarda la imagen.'),
            T('n', 'c', '201 Created', 'res', 'Subida correcta.'),
            T('c', 'n', 'POST /library/libros · 15 MB', 'req', 'Ahora una imagen demasiado grande.', { h: ['POST /library/libros HTTP/1.1', 'Content-Length: 15728640'] }),
            K('n', '15 MB > 10 MB ✘', 'NGINX rechaza ANTES de leer el cuerpo: la app no gasta CPU ni memoria. (Sin este ajuste, el límite por defecto de 1 MB rechazaría hasta las portadas normales.)', { kind: 'err', hl: ['client_max_body_size'], post: s => s.fx('n', 'err') }),
            T('n', 'c', '413 Request Entity Too Large', 'err', 'El cliente recibe el error directamente de NGINX.', { h: ['HTTP/1.1 413 Request Entity Too Large', 'Server: nginx'] }),
          ],
        }),
      },
      {
        name: 'App caída (502)', build: () => ({
          setup: s => s.down('app', true, 'DETENIDO'),
          steps: [
            T('c', 'n', 'GET /library/', 'req', 'Petición normal; el cliente no sabe que la app está caída.', { h: ['GET /library/ HTTP/1.1'] }),
            K('n', 'proxy_pass → 127.0.0.1:3000', 'NGINX intenta conectar al upstream.', { hl: ['proxy_pass http://127.0.0.1:3000'] }),
            T('n', 'app', 'TCP SYN :3000', 'tcp', 'Intento de conexión con proxy_connect_timeout de 5 s.', { hl: ['proxy_connect_timeout'] }),
            T('app', 'n', 'RST · connection refused', 'err', 'Nadie escucha en el 3000: el sistema operativo rechaza (RST). Si el host no respondiera, NGINX esperaría los 5 s y daría 504.', { h: ['connect() failed (111: Connection refused)', 'while connecting to upstream  ← error.log'] }),
            K('n', 'upstream no disponible', 'NGINX registra el fallo en error.log y construye la respuesta de error. La app caída NO tumba a NGINX.', { kind: 'err', post: s => s.fx('n', 'err') }),
            T('n', 'c', '502 Bad Gateway', 'err', 'El cliente recibe 502: "el proxy está bien, el servidor de atrás no". Con un balanceador, aquí se probaría otro servidor.', { h: ['HTTP/1.1 502 Bad Gateway', 'Server: nginx'] }),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* 3. API GATEWAY                                                        */
  /* ===================================================================== */
  const gwNodes = [
    N('c', 'Clientes', 'Electron·PythonTk·Java', 120, 235, { icon: '💻', kind: 'client', w: 196 }),
    N('g', 'API Gateway', 'NGINX :80', 470, 235, { icon: '🚪', kind: 'proxy', w: 170 }),
    N('login', 'Login', ':5000', 860, 40, { icon: '🔑', w: 130, h: 40 }),
    N('libros', 'Libros', ':5001', 860, 120, { icon: '📚', w: 130, h: 40 }),
    N('users', 'Users', ':5002', 860, 200, { icon: '👤', w: 130, h: 40 }),
    N('authors', 'Authors', ':5003', 860, 280, { icon: '✍️', w: 130, h: 40 }),
    N('pedidos', 'Pedidos', ':5004', 860, 360, { icon: '🧾', w: 130, h: 40 }),
    N('pagos', 'Pagos', ':5005', 860, 435, { icon: '💳', w: 130, h: 40 }),
  ];
  const gwLinks = [['c', 'g'], ['g', 'login'], ['g', 'libros'], ['g', 'users'], ['g', 'authors'], ['g', 'pedidos'], ['g', 'pagos']];
  const JWT = 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0MiIsInJvbCI6ImNsaWVudGUifQ.sig';
  const gateway = {
    id: 'gateway', tab: 'API Gateway', cmp: 2,
    title: 'API Gateway',
    summary: 'Una sola puerta de entrada para muchos microservicios. Enruta por ruta, reescribe prefijos, limita el ritmo (rate limit) y centraliza health checks. Es un reverse proxy con "inteligencia de API".',
    tags: ['Capa 7 (HTTP/API)', 'NGINX · Kong · AWS API Gateway · Traefik', 'conf.d/01_reverse_proxy.conf'],
    nodes: gwNodes, links: gwLinks,
    codeTitle: 'conf.d/01_reverse_proxy.conf (gateway)',
    code: [
      'limit_req_zone $binary_remote_addr zone=login_zone:10m rate=10r/m;',
      '',
      '# Login: la barra final de proxy_pass QUITA el prefijo /api/auth/',
      'location /api/auth/ { proxy_pass http://127.0.0.1:5000/; }',
      'location = /api/auth/login {',
      '    limit_req zone=login_zone burst=5 nodelay;',
      '    limit_req_status 429;',
      '    proxy_pass http://127.0.0.1:5000/login;',
      '}',
      '',
      '# Libros: prefijo /api/books reescrito a /api/libros',
      'location = /api/books { proxy_pass http://127.0.0.1:5001/api/libros$is_args$args; }',
      'location /api/books/  { proxy_pass http://127.0.0.1:5001/api/libros/; }',
      'location /api/libros  { proxy_pass http://127.0.0.1:5001; }',
      '',
      '# Resto: sin barra final, se conserva la ruta completa',
      'location /api/users    { proxy_pass http://127.0.0.1:5002; }',
      'location /api/authors  { proxy_pass http://127.0.0.1:5003; }',
      'location /api/pedidos  { proxy_pass http://127.0.0.1:5004; }',
      'location /api/pagos    { proxy_pass http://127.0.0.1:5005; }',
      '',
      '# /health/<servicio> -> puerto segun el mapa',
      'location ~ ^/health/(?<svc>login|libros|users|authors|pedidos|pagos|tracking)$ {',
      '    proxy_pass http://127.0.0.1:$svc_port/health;',
      '}',
    ],
    concepts: [
      { t: 'Punto único de entrada', d: 'Los clientes conocen UNA dirección (http://IP). Los puertos 5000-5005 no se exponen ni se memorizan.' },
      { t: 'Enrutamiento por ruta', d: '/api/pedidos → :5004, /api/pagos → :5005… Cada prefijo apunta a un microservicio distinto.' },
      { t: 'Reescritura de prefijo', d: '/api/auth/login → /login (se quita /api/auth). /api/books/book → /api/libros/book (el prefijo público cambia al interno).' },
      { t: 'Rate limit', d: 'limit_req frena fuerza bruta: 10 intentos/min por IP con ráfaga de 5. Lo demás recibe 429 sin tocar el servicio.' },
      { t: 'Autenticación (JWT)', d: 'En este proyecto el gateway SOLO enruta: reenvía Authorization y cada servicio valida firma y expiración. Otros gateways (Kong, AWS) pueden validarlo en la puerta.' },
      { t: 'Observabilidad central', d: '/health/<servicio> y un único access.log. Se cambia un servicio de puerto sin tocar a los clientes.' },
      { t: 'Diferencia con reverse proxy', d: 'Reverse proxy = reenviar a UNA app. Gateway = muchas APIs detrás, con reglas por ruta (límites, auth, versionado).' },
    ],
    scenarios: [
      {
        name: 'GET /api/books/book (prefijo)', build: () => ({
          steps: [
            T('c', 'g', 'GET /api/books/book', 'req', 'El cliente usa el prefijo público /api/books. No sabe que el servicio se llama "libros" ni en qué puerto vive.', { h: ['GET /api/books/book HTTP/1.1', 'Host: 34.10.20.30', 'Accept: application/json'] }),
            K('g', 'location /api/books/\nrewrite → /api/libros/', 'NGINX compara ubicaciones: la de prefijo más largo gana. proxy_pass con URI (/api/libros/) sustituye la parte coincidente: /api/books/ → /api/libros/ y conserva "book".', { hl: ['location /api/books/', 'location = /api/books'] }),
            T('g', 'libros', 'GET /api/libros/book', 'req', 'El servicio recibe SU ruta real. El prefijo público quedó solo en el gateway.', { h: ['GET /api/libros/book HTTP/1.1', 'Host: 34.10.20.30', 'X-Forwarded-For: 201.141.8.77'], hl: ['proxy_pass http://127.0.0.1:5001/api/libros/'] }),
            T('libros', 'g', '200 OK · JSON', 'res', 'El servicio responde al gateway.', { h: ['HTTP/1.1 200 OK', 'Content-Type: application/json', '{"isbn":"978-…","titulo":"…"}'] }),
            T('g', 'c', '200 OK · JSON', 'res', 'El gateway entrega la respuesta. La ruta /api/libros original sigue funcionando por compatibilidad.'),
          ],
        }),
      },
      {
        name: 'Login: /api/auth/login → /login', build: () => ({
          steps: [
            T('c', 'g', 'POST /api/auth/login', 'req', 'El cliente inicia sesión por el prefijo /api/auth.', { h: ['POST /api/auth/login HTTP/1.1', 'Content-Type: application/json', '{"email":"ana@udem.edu","password":"••••••"}'] }),
            K('g', 'location = /api/auth/login\nlimit_req ✔ tokens: 5/5', 'Hay una coincidencia exacta (=) con límite de peticiones. Aún quedan fichas en el "cubo", así que pasa.', { hl: ['location = /api/auth/login', 'limit_req zone'], post: s => s.badge('g', 'login: 4 fichas', 'ok') }),
            T('g', 'login', 'POST /login', 'req', 'proxy_pass con URI /login: se QUITA el prefijo /api/auth. El servicio de login solo conoce /login.', { h: ['POST /login HTTP/1.1', 'X-Forwarded-For: 201.141.8.77'], hl: ['proxy_pass http://127.0.0.1:5000/login'] }),
            T('login', 'g', '200 OK · código enviado', 'res', 'Primer factor correcto: el servicio manda un código al correo y pide /login/verify.', { h: ['HTTP/1.1 200 OK', '{"mensaje":"Código enviado"}'] }),
            T('g', 'c', '200 OK', 'res', 'El cliente continúa con POST /api/auth/login/verify (mismo límite) y recibe su JWT.'),
          ],
        }),
      },
      {
        name: 'POST /api/pedidos con JWT válido', build: () => ({
          steps: [
            T('c', 'g', 'POST /api/pedidos', 'req', 'Compra autenticada: el cliente manda el JWT que recibió al iniciar sesión.', { h: ['POST /api/pedidos HTTP/1.1', JWT, 'Content-Type: application/json', '{"items":[{"isbn":"978-…","cantidad":2}]}'] }),
            K('g', 'location /api/pedidos\nsolo enruta (no valida JWT)', 'En este diseño el gateway NO decide permisos: reenvía la cabecera Authorization intacta. Así la seguridad no depende de un único punto.', { hl: ['location /api/pedidos'] }),
            T('g', 'pedidos', 'POST /api/pedidos', 'req', 'Se conserva la ruta completa (proxy_pass sin barra final) y la cabecera Authorization.', { h: ['POST /api/pedidos HTTP/1.1', JWT, 'X-Forwarded-For: 201.141.8.77'] }),
            K('pedidos', 'valida JWT ✔\nfirma HS256 · exp vigente · rol', 'El microservicio verifica la firma con su secreto, que no haya expirado y el rol. Solo entonces ejecuta la lógica.', { kind: 'res', post: s => s.fx('pedidos', 'ok') }),
            T('pedidos', 'g', '201 Created', 'res', 'Pedido creado.', { h: ['HTTP/1.1 201 Created', '{"id_pedido":1042,"estado":"pagado_pendiente"}'] }),
            T('g', 'c', '201 Created', 'res', 'El cliente recibe la confirmación.'),
          ],
        }),
      },
      {
        name: 'JWT inválido → 401', build: () => ({
          steps: [
            T('c', 'g', 'POST /api/pagos', 'req', 'Petición con un token alterado o vencido.', { h: ['POST /api/pagos HTTP/1.1', 'Authorization: Bearer eyJhbGciOi…TOKEN_MANIPULADO', '{"id_pedido":1042}'] }),
            T('g', 'pagos', 'POST /api/pagos', 'req', 'El gateway no revisa el token: lo reenvía tal cual.', { hl: ['location /api/pagos'] }),
            K('pagos', 'JWT ✘ firma inválida', 'La firma no coincide con el secreto del servicio (o exp ya pasó). No se ejecuta nada.', { kind: 'err', post: s => s.fx('pagos', 'err') }),
            T('pagos', 'g', '401 Unauthorized', 'err', 'El servicio rechaza la petición.', { h: ['HTTP/1.1 401 Unauthorized', '{"mensaje":"Token inválido o expirado"}'] }),
            T('g', 'c', '401 Unauthorized', 'err', 'El cliente debe renovar la sesión (refresh token) o volver a iniciar sesión.'),
          ],
        }),
      },
      {
        name: 'Fuerza bruta en login → 429', build: () => ({
          setup: s => s.badge('g', 'login: 5 fichas', 'ok'),
          steps: [
            T('c', 'g', 'login #1 (clave incorrecta)', 'req', 'Un atacante prueba contraseñas sin parar. La zona login_zone permite 10/min por IP, con ráfaga (burst) de 5.', { h: ['POST /api/auth/login', '{"email":"ana@udem.edu","password":"intento1"}'], hl: ['limit_req_zone', 'limit_req zone'] }),
            T('g', 'login', 'POST /login', 'req', 'Pasa: quedan fichas.', { post: s => s.badge('g', 'login: 4 fichas', 'ok') }),
            T('login', 'c', '401 clave incorrecta', 'err', 'El servicio contesta 401 directo hasta el cliente (por el gateway).'),
            T('c', 'g', 'login #2', 'req', 'Segundo intento inmediato.', { dur: 700 }),
            T('g', 'login', 'POST /login', 'req', 'Pasa.', { dur: 700, post: s => s.badge('g', 'login: 3 fichas', 'warn') }),
            T('c', 'g', 'login #3', 'req', 'Tercer intento.', { dur: 700 }),
            T('g', 'login', 'POST /login', 'req', 'Pasa.', { dur: 700, post: s => s.badge('g', 'login: 1 ficha', 'warn') }),
            K('g', 'intentos #4–#6 pasan (ráfaga)\ncubo vacío → burst agotado', 'La ráfaga de 5 se consume rápido; después solo entra 1 intento cada 6 s (rate=10r/m). Se omiten #4-#6 para abreviar.', { kind: 'err', post: s => s.badge('g', 'login: 0 fichas', 'err') }),
            T('c', 'g', 'login #7', 'req', 'Séptimo intento en menos de un segundo.', { h: ['POST /api/auth/login', '{"password":"intento7"}'] }),
            K('g', 'limit_req ✘ excede rate+burst', 'El gateway ni abre conexión al servicio de login: responde 429 por sí mismo y registra el rechazo. Un ataque no consume recursos del microservicio.', { kind: 'err', hl: ['limit_req_status 429'], post: s => s.fx('g', 'err') }),
            T('g', 'c', '429 Too Many Requests', 'err', 'El atacante queda frenado. Un usuario legítimo que espera unos segundos vuelve a pasar. El login nunca vio el intento #7.', { h: ['HTTP/1.1 429 Too Many Requests', 'Server: nginx'] }),
          ],
        }),
      },
      {
        name: 'Health check por servicio', build: () => ({
          steps: [
            T('c', 'g', 'GET /health/pagos', 'health', 'El cliente PythonTk pinta el semáforo de cada servicio. Todos los servicios exponen /health, pero con un solo host se distingue por la ruta.', { h: ['GET /health/pagos HTTP/1.1'] }),
            K('g', 'regex ^/health/(?<svc>…)$\n$svc=pagos → map → 5005', 'La ruta con expresión regular captura el nombre del servicio; un map lo convierte a puerto. Una sola regla cubre los siete servicios.', { kind: 'health', hl: ['location ~ ^/health', 'proxy_pass http://127.0.0.1:$svc_port/health'] }),
            T('g', 'pagos', 'GET /health', 'health', 'El gateway llama al /health real del servicio.', { h: ['GET /health HTTP/1.1'] }),
            T('pagos', 'g', '200 {db:ok, redis:ok}', 'res', 'El servicio comprueba su base de datos y Redis.', { h: ['HTTP/1.1 200 OK', '{"db":"ok","redis":"ok"}'] }),
            T('g', 'c', '200 {db:ok, redis:ok}', 'res', 'El cliente lo pinta en VERDE. Si la BD estuviera caída vendría 503 y se pintaría en amarillo.'),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* 4. BALANCEADOR DE CARGA                                               */
  /* ===================================================================== */
  const ALGOS = {
    rr: 'Round Robin (turnos)',
    weighted: 'Ponderado (pesos 3 · 1 · 1)',
    least: 'Menos conexiones (least_conn)',
    iphash: 'Hash de IP (ip_hash, sesión pegajosa)',
    random: 'Aleatorio',
  };
  const CLIENTS = ['10.0.0.1', '10.0.0.2', '10.0.0.1', '10.0.0.3', '10.0.0.4', '10.0.0.2', '10.0.0.1', '10.0.0.3'];
  const HOLD = [4, 1, 1, 2, 3, 1, 2, 1]; // cuantas peticiones siguientes mantiene abierta la conexion
  const SV = ['s1', 's2', 's3'];
  const hashIp = ip => [...ip].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7);

  function simulateLB(algo, down, n) {
    const alive = i => !down.includes(SV[i]);
    const counts = [0, 0, 0], active = [0, 0, 0], ends = [];
    const weights = [3, 1, 1], current = [0, 0, 0];
    let turn = 0, seed = 7;
    const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    const out = [];
    for (let k = 0; k < n; k++) {
      for (let j = ends.length - 1; j >= 0; j--) if (ends[j].at <= k) { active[ends[j].s]--; ends.splice(j, 1); }
      const idx = [0, 1, 2].filter(alive);
      const ip = CLIENTS[k];
      let pick = -1, why = '';
      if (!idx.length) { out.push({ k, ip, pick: -1, why: 'ningún servidor sano', counts: [...counts], active: [...active] }); continue; }
      if (algo === 'rr') {
        pick = idx[turn % idx.length]; turn++;
        why = `turno ${turn} → ${SV[pick].toUpperCase()}`;
      } else if (algo === 'weighted') {
        const total = idx.reduce((s, i) => s + weights[i], 0);
        idx.forEach(i => { current[i] += weights[i]; });
        pick = idx.reduce((b, i) => (current[i] > current[b] ? i : b), idx[0]);
        const snap = idx.map(i => `${SV[i].toUpperCase()}=${current[i]}`).join(' ');
        current[pick] -= total;
        why = `pesos actuales ${snap} → mayor: ${SV[pick].toUpperCase()}`;
      } else if (algo === 'least') {
        pick = idx.reduce((b, i) => (active[i] < active[b] ? i : b), idx[0]);
        why = `activas ${idx.map(i => `${SV[i].toUpperCase()}=${active[i]}`).join(' ')} → menor: ${SV[pick].toUpperCase()}`;
      } else if (algo === 'iphash') {
        const h = hashIp(ip);
        pick = idx[h % idx.length];
        why = `hash(${ip}) mod ${idx.length} → ${SV[pick].toUpperCase()} (siempre el mismo)`;
      } else {
        pick = idx[Math.floor(rnd() * idx.length)];
        why = `azar → ${SV[pick].toUpperCase()}`;
      }
      if (down.length) why += `\n(excluye: ${down.map(d => d.toUpperCase()).join(', ')} caído)`;
      counts[pick]++; active[pick]++; ends.push({ at: k + HOLD[k] + 1, s: pick });
      out.push({ k, ip, pick, why, counts: [...counts], active: [...active] });
    }
    return out;
  }

  const lbBadge = (s, counts, active, down) => SV.forEach((id, i) => {
    if (down.includes(id)) s.badge(id, 'DOWN · fuera del pool', 'err');
    else s.badge(id, `peticiones: ${counts[i]} · activas: ${active[i]}`, counts[i] ? 'ok' : '');
  });

  const balancer = {
    id: 'balancer', tab: 'Balanceador de carga', cmp: 3,
    title: 'Balanceador de carga (load balancer)',
    summary: 'Reparte las peticiones entre varios servidores idénticos para dar más capacidad y tolerar fallas. Decide con un algoritmo y saca del pool a los servidores que no responden (health check).',
    tags: ['Capa 4 (TCP) o capa 7 (HTTP)', 'NGINX upstream · HAProxy · AWS ALB/ELB', 'Escalado horizontal + alta disponibilidad'],
    nodes: [
      N('c', 'Clientes', '10.0.0.1 … 10.0.0.4', 110, 235, { icon: '👥', kind: 'client', w: 180 }),
      N('lb', 'Balanceador', 'NGINX upstream', 460, 235, { icon: '⚖️', kind: 'proxy', w: 170 }),
      N('s1', 'Servidor S1', '10.0.1.11:5001', 850, 75, { icon: '🗄️', w: 170 }),
      N('s2', 'Servidor S2', '10.0.1.12:5001', 850, 235, { icon: '🗄️', w: 170 }),
      N('s3', 'Servidor S3', '10.0.1.13:5001', 850, 395, { icon: '🗄️', w: 170 }),
    ],
    links: [['c', 'lb'], ['lb', 's1'], ['lb', 's2'], ['lb', 's3']],
    codeTitle: 'upstream (ejemplo, no está en el proyecto)',
    code: [
      'upstream libros_pool {',
      '    # Elige UN algoritmo (por omisión: round robin):',
      '    # least_conn;      # menos conexiones activas',
      '    # ip_hash;         # misma IP -> mismo servidor',
      '    # random;',
      '    server 10.0.1.11:5001 weight=3 max_fails=2 fail_timeout=30s;',
      '    server 10.0.1.12:5001 weight=1 max_fails=2 fail_timeout=30s;',
      '    server 10.0.1.13:5001 weight=1 max_fails=2 fail_timeout=30s;',
      '    server 10.0.1.14:5001 backup;   # solo si los demas caen',
      '}',
      '',
      'server {',
      '    location /api/libros {',
      '        proxy_pass http://libros_pool;',
      '        # si un servidor falla, reintenta con otro SIN que el cliente lo note',
      '        proxy_next_upstream error timeout http_502 http_503;',
      '    }',
      '}',
    ],
    options: [
      { id: 'algo', label: 'Algoritmo', type: 'select', values: Object.entries(ALGOS).map(([v, l]) => [v, l]), def: 'rr' },
      { id: 'n', label: 'Peticiones', type: 'select', values: [['4', '4'], ['6', '6'], ['8', '8']], def: '6' },
      { id: 'down', label: 'Caídos', type: 'checks', values: [['s1', 'S1'], ['s2', 'S2'], ['s3', 'S3']], def: [] },
    ],
    concepts: [
      { t: 'Round Robin', d: 'Turnos 1-2-3-1-2-3. Simple y justo si todas las peticiones cuestan lo mismo y los servidores son iguales.' },
      { t: 'Ponderado (weight)', d: 'Servidores más potentes reciben más tráfico (3:1:1). NGINX usa "smooth weighted round-robin" para no mandar ráfagas seguidas.' },
      { t: 'Least connections', d: 'Manda al que tiene MENOS conexiones activas. Ideal cuando hay peticiones largas y cortas mezcladas.' },
      { t: 'IP hash (sticky)', d: 'La misma IP cae siempre en el mismo servidor: útil si la sesión vive en memoria. Si ese servidor cae, esa IP se reasigna.' },
      { t: 'Health check', d: 'Activo (el balanceador sondea /health cada N s) o pasivo (max_fails/fail_timeout tras errores reales). El servidor caído sale del pool.' },
      { t: 'Failover transparente', d: 'proxy_next_upstream reintenta en otro servidor: el cliente no ve el error. "backup" entra solo cuando los demás caen.' },
      { t: 'Capa 4 vs capa 7', d: 'L4 (stream/TCP) reparte conexiones sin leer HTTP. L7 puede decidir por ruta, cabeceras o cookies.' },
      { t: 'Sin estado en el servidor', d: 'Para escalar de verdad, la sesión debe vivir fuera (Redis/JWT, como en este proyecto) y no depender del servidor.' },
    ],
    scenarios: [
      {
        name: 'Repartir peticiones', build: o => {
          const algo = o.algo || 'rr', down = o.down || [], n = +(o.n || 6);
          const sim = simulateLB(algo, down, n), steps = [];
          sim.forEach(r => {
            const label = `c${r.k + 1} · ${r.ip}`;
            steps.push(T('c', 'lb', label + ' GET /api/libros', 'req', `Petición #${r.k + 1} desde ${r.ip}.`, { h: [`GET /api/libros HTTP/1.1`, `X-Real-IP: ${r.ip}`] }));
            if (r.pick < 0) {
              steps.push(K('lb', 'sin servidores sanos', 'Todos los servidores están marcados DOWN: no hay a dónde enviar.', { kind: 'err' }));
              steps.push(T('lb', 'c', '503 Service Unavailable', 'err', 'El balanceador responde por sí mismo con 503.'));
              return;
            }
            const sid = SV[r.pick];
            steps.push(K('lb', `${ALGOS[algo].split(' (')[0]}\n${r.why}`, `Algoritmo: ${ALGOS[algo]}. ${r.why.replace('\n', ' ')}`, { hl: algo === 'rr' ? ['server 10.0.1.11'] : algo === 'weighted' ? ['weight='] : algo === 'least' ? ['least_conn'] : algo === 'iphash' ? ['ip_hash'] : ['random;'] }));
            steps.push(T('lb', sid, 'GET /api/libros', 'req', `El balanceador abre (o reutiliza) una conexión con ${sid.toUpperCase()}.`, { hl: ['proxy_pass http://libros_pool'], post: s => lbBadge(s, r.counts, r.active, down) }));
            steps.push(T(sid, 'lb', '200 OK', 'res', `${sid.toUpperCase()} procesa la petición y responde al balanceador.`, { h: ['HTTP/1.1 200 OK', `X-Servido-Por: ${sid.toUpperCase()}`] }));
            steps.push(T('lb', 'c', '200 OK', 'res', 'El cliente recibe la respuesta sin saber qué servidor la atendió.'));
          });
          return { setup: s => { lbBadge(s, [0, 0, 0], [0, 0, 0], down); down.forEach(d => s.down(d, true, 'DOWN · fuera del pool')); }, steps };
        },
      },
      {
        name: 'Health check y failover', build: () => ({
          setup: s => lbBadge(s, [0, 0, 0], [0, 0, 0], []),
          steps: [
            K('lb', 'health check activo\ncada 5 s a /health', 'El balanceador sondea a cada servidor de forma periódica, aunque no haya tráfico de clientes.', { kind: 'health' }),
            T('lb', 's1', 'GET /health', 'health', 'Sonda a S1.', { dur: 800 }), T('s1', 'lb', '200 ok', 'res', 'S1 sano.', { dur: 800 }),
            T('lb', 's2', 'GET /health', 'health', 'Sonda a S2.', { dur: 800 }), T('s2', 'lb', '200 ok', 'res', 'S2 sano.', { dur: 800 }),
            T('lb', 's3', 'GET /health', 'health', 'Sonda a S3.', { dur: 800 }), T('s3', 'lb', '200 ok', 'res', 'S3 sano. Los tres están en el pool.', { dur: 800 }),
            K('s2', '💥 el proceso de S2 se cae', 'S2 deja de responder (crash, reinicio, red cortada). El balanceador todavía NO lo sabe.', { kind: 'err', post: s => { s.down('s2', true, 'sin respuesta'); } }),
            T('c', 'lb', 'GET /api/libros', 'req', 'Llega una petición y, por turno, le toca a S2.', { h: ['GET /api/libros HTTP/1.1'] }),
            T('lb', 's2', 'GET /api/libros', 'req', 'El balanceador intenta conectar con S2.', { dur: 900 }),
            T('s2', 'lb', 'connect() failed · refused', 'err', 'Fallo real de conexión: así se detecta de forma PASIVA (max_fails). Cuenta 1 de 2.', { h: ['connect() failed (111: Connection refused) while connecting to upstream', 'upstream: "http://10.0.1.12:5001/api/libros"'], hl: ['max_fails=2'], post: s => s.badge('lb', 'S2: fallo 1/2', 'warn') }),
            K('lb', 'proxy_next_upstream\nreintenta con el siguiente', 'En vez de devolver un error, el balanceador reintenta la MISMA petición con otro servidor.', { hl: ['proxy_next_upstream'] }),
            T('lb', 's3', 'GET /api/libros (reintento)', 'req', 'Reintento transparente hacia S3.', { dur: 900 }),
            T('s3', 'lb', '200 OK', 'res', 'S3 responde.', { dur: 900, post: s => s.badge('s3', 'peticiones: 1 · activas: 0', 'ok') }),
            T('lb', 'c', '200 OK', 'res', 'El cliente recibe 200: NO notó la falla de S2. Eso es alta disponibilidad.'),
            T('lb', 's2', 'GET /health', 'health', 'El siguiente sondeo activo vuelve a probar S2.', { dur: 800 }),
            T('s2', 'lb', 'timeout', 'err', 'Segundo fallo: llega a max_fails=2.', { dur: 800 }),
            K('lb', 'S2 marcado DOWN\nfail_timeout=30 s', 'Con 2 fallos, NGINX deja S2 fuera del pool durante fail_timeout (30 s). Ya no recibe tráfico.', { kind: 'err', hl: ['fail_timeout=30s'], post: s => s.badge('s2', 'DOWN · fuera del pool', 'err') }),
            T('c', 'lb', 'GET /api/libros', 'req', 'Nueva petición: S2 ya ni se considera.'),
            T('lb', 's1', 'GET /api/libros', 'req', 'Va a S1 (S2 excluido).', { dur: 900 }),
            T('s1', 'lb', '200 OK', 'res', 'S1 responde.', { dur: 900, post: s => s.badge('s1', 'peticiones: 1 · activas: 0', 'ok') }),
            T('lb', 'c', '200 OK', 'res', 'Sin errores para el cliente.', { dur: 900 }),
            K('s2', '🔧 S2 se reinicia', 'El equipo de operaciones (o el orquestador) levanta S2 de nuevo.', { kind: 'res', post: s => s.down('s2', false, 'levantado') }),
            T('lb', 's2', 'GET /health', 'health', 'Pasado fail_timeout, el balanceador vuelve a probar S2.', { dur: 800 }),
            T('s2', 'lb', '200 ok', 'res', 'S2 responde bien.', { dur: 800 }),
            K('lb', 'S2 reincorporado al pool', 'S2 vuelve a recibir tráfico. (En NGINX Plus, slow_start sube su carga poco a poco para no saturarlo recién arrancado.)', { kind: 'res', post: s => s.badge('s2', 'de vuelta en el pool', 'ok') }),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* 5. PORT FORWARD (TCP / stream)                                        */
  /* ===================================================================== */
  const tcpNodes = [
    N('c', 'Cliente', 'curl · app', 120, 235, { icon: '💻', kind: 'client' }),
    N('n', 'NGINX stream', ':15001  (capa 4)', 480, 235, { icon: '🔀', kind: 'proxy', w: 176 }),
    N('s', 'Libros', '127.0.0.1:5001', 850, 235, { icon: '📚' }),
  ];
  const portfwd = {
    id: 'portfwd', tab: 'Port forward (TCP)', cmp: 4,
    title: 'Port forward (reenvío de puerto TCP)',
    summary: 'Reenvía bytes de un puerto a otro sin entender el protocolo. NGINX con el módulo stream no lee HTTP: abre una conexión TCP al destino y copia lo que pasa en ambos sentidos.',
    tags: ['Capa 4 (TCP)', 'NGINX stream · iptables DNAT · ssh -L · socat', 'stream.d/02_port_forward.conf'],
    nodes: tcpNodes, links: [['c', 'n'], ['n', 's']],
    codeTitle: 'stream.d/02_port_forward.conf',
    code: [
      '# Contexto "stream" (TCP), NO "http". Va en nginx.conf a nivel raiz.',
      'server {',
      '    listen 15001;                      # puerto publico',
      '    proxy_pass 127.0.0.1:5001;         # destino interno (libros)',
      '    proxy_connect_timeout 5s;',
      '}',
      'server {',
      '    listen 15004;',
      '    proxy_pass 127.0.0.1:5004;         # pedidos',
      '}',
      'server {',
      '    listen 15005;',
      '    proxy_pass 127.0.0.1:5005;         # pagos',
      '}',
    ],
    concepts: [
      { t: 'No entiende HTTP', d: 'No hay location, cabeceras, reescritura, límites ni caché: solo ip:puerto de entrada y de salida.' },
      { t: 'Dos conexiones TCP', d: 'Cliente↔NGINX y NGINX↔destino. NGINX copia bytes entre ambas hasta que alguna se cierra.' },
      { t: 'Sirve para cualquier protocolo', d: 'HTTP, MySQL, SSH, Redis, MQTT… Cualquier servicio TCP (con UDP: listen … udp).' },
      { t: 'Qué ve el destino', d: 'La IP de NGINX como origen (a menos que se use proxy_protocol o transparent). Por eso no hay X-Forwarded-For.' },
      { t: 'Cuándo usarlo', d: 'Exponer UN servicio concreto sin pasar por las reglas del gateway o cuando el protocolo no es HTTP.' },
      { t: 'Cuidado', d: 'Al no filtrar nada, quien llegue al puerto llega al servicio: hay que limitarlo con firewall o allow/deny.' },
    ],
    scenarios: [
      {
        name: 'Conexión y datos', build: () => ({
          steps: [
            T('c', 'n', 'SYN', 'tcp', 'El cliente inicia el three-way handshake con el puerto público 15001.', { h: ['TCP SYN  → 34.10.20.30:15001'], hl: ['listen 15001'] }),
            T('n', 'c', 'SYN-ACK', 'tcp', 'NGINX acepta la conexión.'),
            T('c', 'n', 'ACK', 'tcp', 'Conexión 1 establecida (cliente ↔ NGINX).'),
            K('n', 'server { listen 15001 }\n→ proxy_pass 127.0.0.1:5001', 'NGINX NO lee ningún dato todavía: solo sabe que entró una conexión por el puerto 15001 y que su destino es 127.0.0.1:5001.', { kind: 'tcp', hl: ['proxy_pass 127.0.0.1:5001'] }),
            T('n', 's', 'SYN', 'tcp', 'NGINX abre la conexión 2 hacia el destino.', { hl: ['proxy_connect_timeout'] }),
            T('s', 'n', 'SYN-ACK', 'tcp', 'Libros acepta.'),
            T('n', 's', 'ACK', 'tcp', 'Conexión 2 establecida (NGINX ↔ libros).'),
            T('c', 'n', 'bytes: "GET /health…"', 'tcp', 'El cliente manda sus datos. Para NGINX son bytes opacos; casualmente son HTTP.', { h: ['47 45 54 20 2f 68 65 61 6c 74 68 …', '("GET /health HTTP/1.1…" en hexadecimal)', 'NGINX no lo interpreta'] }),
            T('n', 's', 'bytes (idénticos)', 'tcp', 'Se copian tal cual al destino: sin cabeceras añadidas, sin reescritura.'),
            T('s', 'n', 'bytes: "200 OK {db:ok}"', 'tcp', 'La respuesta vuelve por la conexión 2.', { h: ['HTTP/1.1 200 OK', '{"db":"ok","redis":"ok"}'] }),
            T('n', 'c', 'bytes (idénticos)', 'tcp', 'Y se copia a la conexión 1.'),
            T('c', 'n', 'FIN', 'tcp', 'El cliente cierra.'),
            T('n', 's', 'FIN', 'tcp', 'NGINX propaga el cierre: ambas conexiones terminan juntas.'),
          ],
        }),
      },
      {
        name: 'Destino caído', build: () => ({
          setup: s => s.down('s', true, 'DETENIDO'),
          steps: [
            T('c', 'n', 'SYN', 'tcp', 'El cliente conecta al 15001.'), T('n', 'c', 'SYN-ACK', 'tcp', 'NGINX acepta primero: acepta el cliente ANTES de saber si el destino responde.'),
            T('c', 'n', 'ACK', 'tcp', 'Conexión 1 abierta.'),
            T('n', 's', 'SYN', 'tcp', 'NGINX intenta la conexión 2.'),
            T('s', 'n', 'RST (refused)', 'err', 'Nadie escucha en 5001: se rechaza.', { h: ['connect() failed (111: Connection refused) while connecting to upstream'] }),
            T('n', 'c', 'FIN / RST', 'err', 'NGINX cierra la conexión del cliente. En TCP no hay códigos 502: el cliente solo ve que la conexión se cortó.', { post: s => s.fx('n', 'err') }),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* 6. WEBSOCKET                                                          */
  /* ===================================================================== */
  const wsNodes = [
    N('c', 'Cliente Java', 'mapa de rastreo', 120, 235, { icon: '🗺️', kind: 'client' }),
    N('n', 'NGINX WebSocket', ':8090 (exclusivo)', 480, 235, { icon: '🔌', kind: 'proxy', w: 180 }),
    N('t', 'Servidor de rastreo', '127.0.0.1:5006', 850, 235, { icon: '📍', w: 176 }),
  ];
  const websocket = {
    id: 'websocket', tab: 'WebSocket exclusivo', cmp: 5,
    title: 'Proxy de WebSocket (conexión exclusiva)',
    summary: 'HTTP normal es petición→respuesta. WebSocket empieza como HTTP, pide "Upgrade" y se convierte en un canal bidireccional que dura minutos u horas. Por eso va en su propio servidor, con timeouts largos.',
    tags: ['Capa 7 (HTTP → WebSocket)', 'NGINX · HAProxy · Envoy', 'conf.d/03_websocket.conf'],
    nodes: wsNodes, links: [['c', 'n'], ['n', 't']],
    codeTitle: 'conf.d/03_websocket.conf',
    code: [
      'map $http_upgrade $connection_upgrade {',
      "    default upgrade;",
      "    ''      close;",
      '}',
      '',
      'server {',
      '    listen 8090;',
      '    location /ws/ {',
      '        if ($http_upgrade != "websocket") { return 426; }',
      '        proxy_pass http://127.0.0.1:5006;',
      '        proxy_http_version 1.1;                       # el Upgrade exige 1.1',
      '        proxy_set_header Upgrade    $http_upgrade;',
      '        proxy_set_header Connection $connection_upgrade;',
      '        proxy_read_timeout 3600s;   # la conexion vive mientras dura el recorrido',
      '        proxy_send_timeout 3600s;',
      '    }',
      '    location / { return 404; }',
      '}',
    ],
    concepts: [
      { t: 'Handshake HTTP', d: 'GET con Upgrade: websocket y Sec-WebSocket-Key. Si el servidor acepta responde 101 Switching Protocols.' },
      { t: 'Cabeceras hop-by-hop', d: 'Upgrade y Connection NO se reenvían solas por un proxy: hay que pasarlas explícitamente (proxy_set_header) y usar HTTP/1.1.' },
      { t: 'Canal bidireccional', d: 'Tras el 101 ya no hay peticiones/respuestas: ambos lados envían frames cuando quieran (posiciones del repartidor en vivo).' },
      { t: 'Timeouts largos', d: 'proxy_read_timeout por omisión es 60 s: sin frames en ese lapso NGINX cortaría la conexión. Aquí se sube a 3600 s.' },
      { t: 'Servidor exclusivo', d: 'Puerto 8090 solo para WS: sin límites ni timeouts de la API, y una petición HTTP normal recibe 426.' },
      { t: 'Estado en el proxy', d: 'Cada WS mantiene una conexión abierta en NGINX y otra en el backend. Muchos clientes = muchas conexiones largas (worker_connections).' },
    ],
    scenarios: [
      {
        name: 'Handshake y rastreo en vivo', build: () => ({
          steps: [
            T('c', 'n', 'GET /ws/rastreo · Upgrade', 'req', 'El cliente abre el WebSocket con una petición HTTP normal que pide cambiar de protocolo.', { h: ['GET /ws/rastreo HTTP/1.1', 'Host: 34.10.20.30:8090', 'Upgrade: websocket', 'Connection: Upgrade', 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==', 'Sec-WebSocket-Version: 13'] }),
            K('n', '$http_upgrade == "websocket" ✔\nlocation /ws/', 'La condición exclusiva: solo pasan handshakes WebSocket. map calcula Connection: upgrade porque el cliente mandó Upgrade.', { hl: ['if ($http_upgrade', 'map $http_upgrade'] }),
            T('n', 't', 'GET /ws/rastreo · Upgrade', 'req', 'NGINX reenvía el handshake. Sin proxy_set_header Upgrade/Connection el backend recibiría una petición HTTP normal y rechazaría el WebSocket.', { h: ['GET /ws/rastreo HTTP/1.1', 'Upgrade: websocket', 'Connection: upgrade', 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=='], hl: ['proxy_set_header Upgrade', 'proxy_set_header Connection', 'proxy_http_version 1.1'] }),
            T('t', 'n', '101 Switching Protocols', 'ws', 'El servidor acepta el cambio de protocolo.', { h: ['HTTP/1.1 101 Switching Protocols', 'Upgrade: websocket', 'Connection: Upgrade', 'Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo='] }),
            T('n', 'c', '101 Switching Protocols', 'ws', 'El cliente recibe el 101. A partir de aquí el canal ya no es HTTP.', { post: s => { s.badge('n', 'conexión WS abierta', 'ok'); s.link('c', 'n', 'ws'); s.link('n', 't', 'ws'); } }),
            T('t', 'n', 'frame · pos #1 {lat 25.67, lng −100.31}', 'ws', 'El servidor EMPUJA datos sin que el cliente los pida (el repartidor se mueve).', { h: ['frame texto', '{"lat":25.6714,"lng":-100.3098,"estado":"en_camino"}'] }),
            T('n', 'c', 'frame · pos #1', 'ws', 'NGINX copia el frame al cliente: el mapa mueve el marcador.'),
            T('t', 'n', 'frame · pos #2', 'ws', 'Segundo punto del recorrido.', { dur: 900 }),
            T('n', 'c', 'frame · pos #2', 'ws', 'El marcador avanza.', { dur: 900 }),
            T('c', 'n', 'frame · ping', 'ws', 'El cliente también puede hablar: la comunicación es bidireccional sobre la misma conexión.', { dur: 900 }),
            T('n', 't', 'frame · ping', 'ws', 'Se reenvía al servidor.', { dur: 900 }),
            T('t', 'n', 'frame · pong', 'ws', 'Respuesta de mantenimiento: también evita que proxy_read_timeout (3600 s) cierre una conexión inactiva.', { dur: 900, hl: ['proxy_read_timeout 3600s'] }),
            T('n', 'c', 'frame · pong', 'ws', 'Llega al cliente.', { dur: 900 }),
            T('c', 'n', 'close 1000', 'ws', 'El recorrido terminó: el cliente cierra con el código 1000 (cierre normal).', { post: s => { s.link('c', 'n', ''); s.link('n', 't', ''); s.badge('n', '', ''); } }),
            T('n', 't', 'close 1000', 'ws', 'NGINX propaga el cierre y libera ambas conexiones.'),
          ],
        }),
      },
      {
        name: 'HTTP normal a /ws/ → 426', build: () => ({
          steps: [
            T('c', 'n', 'GET /ws/rastreo (sin Upgrade)', 'req', 'Alguien abre la URL del WebSocket en un navegador o con curl, sin pedir Upgrade.', { h: ['GET /ws/rastreo HTTP/1.1', 'Host: 34.10.20.30:8090', '(sin cabecera Upgrade)'] }),
            K('n', '$http_upgrade = "" ≠ "websocket"\n→ return 426', 'El servidor es EXCLUSIVO de WebSocket: una petición que no sea handshake se corta en NGINX.', { kind: 'err', hl: ['return 426'], post: s => s.fx('n', 'err') }),
            T('n', 'c', '426 Upgrade Required', 'err', 'El backend nunca fue contactado. El código 426 indica "usa otro protocolo".', { h: ['HTTP/1.1 426 Upgrade Required'] }),
          ],
        }),
      },
      {
        name: 'Otra ruta → 404', build: () => ({
          steps: [
            T('c', 'n', 'GET /api/libros', 'req', 'Alguien intenta usar el puerto 8090 como si fuera la API.', { h: ['GET /api/libros HTTP/1.1', 'Host: 34.10.20.30:8090'] }),
            K('n', 'location / → return 404', 'Este servidor no tiene más rutas que /ws/: todo lo demás es 404. La API y los WebSockets no se mezclan.', { kind: 'err', hl: ['location / { return 404; }'], post: s => s.fx('n', 'err') }),
            T('n', 'c', '404 Not Found', 'err', 'Respuesta inmediata de NGINX.'),
          ],
        }),
      },
      {
        name: 'Conexión inactiva (timeouts)', build: () => ({
          steps: [
            T('c', 'n', 'handshake WS', 'ws', 'Un WebSocket ya establecido (resumen del handshake).', { dur: 800, post: s => { s.badge('n', 'conexión WS abierta', 'ok'); s.link('c', 'n', 'ws'); s.link('n', 't', 'ws'); } }),
            K('n', 'proxy_read_timeout 3600 s\nsin frames…', 'NGINX cuenta el tiempo SIN datos del backend. Con el valor por omisión (60 s) un recorrido tranquilo se cortaría.', { hl: ['proxy_read_timeout 3600s'] }),
            K('t', 'sin movimiento por un rato', 'El repartidor está detenido: no hay frames. Mientras no pasen 3600 s, la conexión sigue abierta.', {}),
            T('t', 'n', 'frame · pong (keep-alive)', 'ws', 'Un ping/pong periódico reinicia el contador y mantiene vivos NAT y firewalls intermedios.'),
            T('n', 'c', 'frame · pong', 'ws', 'El cliente sabe que el enlace sigue vivo.'),
            K('n', 'si pasan 3600 s sin frames\n→ NGINX cierra', 'Si nadie envía nada en una hora, NGINX corta para no acumular conexiones muertas. El cliente debe reconectar (el cliente Java reintenta).', { kind: 'err', post: s => { s.link('c', 'n', ''); s.link('n', 't', ''); s.badge('n', '', ''); } }),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* 7. TODO JUNTO — ESTE PROYECTO                                         */
  /* ===================================================================== */
  const all = {
    id: 'todo', tab: 'Todo junto (este proyecto)', cmp: -1,
    title: 'Todo junto: la arquitectura de este proyecto',
    summary: 'Los tres clientes de escritorio (Electron, PythonTk y Java) entran por NGINX, que cumple varios papeles a la vez gracias a sus 3 archivos: reverse proxy + API gateway (:80), port forward TCP (:15001/15004/15005) y WebSockets exclusivos (:8090).',
    tags: ['01_reverse_proxy.conf', '02_port_forward.conf', '03_websocket.conf'],
    nodes: [
      N('el', 'Electron', 'catálogo XML', 110, 70, { icon: '⚛️', kind: 'client', w: 150 }),
      N('py', 'PythonTk', 'administración', 110, 235, { icon: '🐍', kind: 'client', w: 150 }),
      N('jv', 'Java FX', 'compra + rastreo', 110, 400, { icon: '☕', kind: 'client', w: 150 }),
      N('http', '01 reverse proxy / gateway', ':80', 470, 100, { icon: '🚪', kind: 'proxy', w: 210 }),
      N('tcp', '02 port forward', ':15001 · 15004 · 15005', 470, 235, { icon: '🔀', kind: 'proxy', w: 210 }),
      N('wsn', '03 WebSocket exclusivo', ':8090', 470, 370, { icon: '🔌', kind: 'proxy', w: 210 }),
      N('mono', 'Monolito', ':3000', 860, 35, { icon: '🖥️', w: 130, h: 40 }),
      N('login', 'Login', ':5000', 860, 105, { icon: '🔑', w: 130, h: 40 }),
      N('libros', 'Libros', ':5001', 860, 175, { icon: '📚', w: 130, h: 40 }),
      N('pedidos', 'Pedidos', ':5004', 860, 245, { icon: '🧾', w: 130, h: 40 }),
      N('pagos', 'Pagos', ':5005', 860, 315, { icon: '💳', w: 130, h: 40 }),
      N('track', 'Rastreo', ':5006', 860, 405, { icon: '📍', w: 130, h: 40 }),
    ],
    links: [['el', 'http'], ['py', 'http'], ['jv', 'http'], ['jv', 'wsn'], ['py', 'tcp'], ['http', 'mono'], ['http', 'login'], ['http', 'libros'], ['http', 'pedidos'], ['http', 'pagos'], ['tcp', 'libros'], ['wsn', 'track']],
    codeTitle: 'Los 3 archivos de deploy/nginx/',
    code: [
      '# conf.d/01_reverse_proxy.conf   (HTTP :80)',
      'location /api/libros   { proxy_pass http://127.0.0.1:5001; }',
      'location /api/pedidos  { proxy_pass http://127.0.0.1:5004; }',
      'location /api/auth/ { proxy_pass http://127.0.0.1:5000/; }',
      'location = /api/auth/login { limit_req zone=login_zone burst=5 nodelay; … }',
      'location /   { proxy_pass http://127.0.0.1:3000; }',
      'location ~ ^/health/(?<svc>login|libros|users|authors|pedidos|pagos|tracking)$ { … }',
      '',
      '# stream.d/02_port_forward.conf   (TCP)',
      'listen 15001;  proxy_pass 127.0.0.1:5001;',
      '',
      '# conf.d/03_websocket.conf   (WS :8090)',
      'location /ws/ { proxy_pass http://127.0.0.1:5006; … }',
    ],
    concepts: [
      { t: '¿Dónde está cada cosa?', d: 'Reverse proxy y gateway son el MISMO NGINX en :80 (01). El port forward trabaja en capa 4 (02) y los WebSockets tienen su servidor (03).' },
      { t: 'Clientes sin puertos', d: 'Electron, PythonTk y Java solo conocen http://IP. En modo gateway las seis URLs se derivan de un host.' },
      { t: 'Seguridad en capas', d: 'NGINX limita (429), recorta cuerpos (413) y oculta puertos; cada microservicio valida su JWT.' },
      { t: 'Balanceador', d: 'Hoy cada servicio tiene UNA instancia. Cambiar proxy_pass por un upstream con varias instancias convertiría el mismo gateway en balanceador.' },
    ],
    scenarios: [
      {
        name: 'PythonTk: semáforo de salud', build: () => ({
          steps: [
            T('py', 'http', 'GET /health/libros', 'health', 'PythonTk (modo gateway) consulta el estado de cada servicio por /health/<servicio>.', { h: ['GET /health/libros HTTP/1.1'], hl: ['location ~ ^/health'] }),
            T('http', 'libros', 'GET /health', 'health', 'El gateway traduce la ruta al puerto 5001.'),
            T('libros', 'http', '200 {db:ok}', 'res', 'Servicio y base de datos funcionando.'),
            T('http', 'py', '200 {db:ok}', 'res', 'El semáforo de Libros se pinta en verde.'),
          ],
        }),
      },
      {
        name: 'Electron: catálogo', build: () => ({
          steps: [
            T('el', 'http', 'GET /api/libros/catalogo', 'req', 'Electron usa solo la URL base http://IP (sin puerto) y el endpoint del catálogo.', { h: ['GET /api/libros/catalogo HTTP/1.1', 'Accept: application/xml'], hl: ['location /api/libros'] }),
            T('http', 'libros', 'GET /api/libros/catalogo', 'req', 'Se conserva la ruta completa y se enruta al servicio de libros.'),
            T('libros', 'http', '200 OK · XML', 'res', 'El servicio devuelve el catálogo en XML.'),
            T('http', 'el', '200 OK · XML', 'res', 'Electron parsea el XML y pinta las tarjetas con paginación.'),
          ],
        }),
      },
      {
        name: 'Java: login y compra', build: () => ({
          steps: [
            T('jv', 'http', 'POST /api/auth/login', 'req', 'El cliente Java inicia sesión por el prefijo /api/auth.', { hl: ['location = /api/auth/login'] }),
            K('http', 'limit_req ✔\nquita /api/auth → /login', 'Rate limit del login y reescritura de prefijo en una sola regla.', { hl: ['limit_req zone'] }),
            T('http', 'login', 'POST /login', 'req', 'El login recibe su ruta interna.'),
            T('login', 'http', '200 OK · JWT', 'res', 'Credenciales correctas: devuelve el token.'),
            T('http', 'jv', '200 OK · JWT', 'res', 'Java guarda el token en la sesión.'),
            T('jv', 'http', 'POST /api/pedidos + JWT', 'req', 'La compra lleva Authorization: Bearer.', { hl: ['location /api/pedidos'] }),
            T('http', 'pedidos', 'POST /api/pedidos + JWT', 'req', 'El gateway solo enruta: reenvía el token intacto.'),
            K('pedidos', 'valida JWT ✔', 'Pedidos verifica firma y expiración.', { kind: 'res', post: s => s.fx('pedidos', 'ok') }),
            T('pedidos', 'http', '201 Created', 'res', 'Pedido registrado.'),
            T('http', 'jv', '201 Created', 'res', 'Java muestra la confirmación y sigue con el pago en /api/pagos.'),
          ],
        }),
      },
      {
        name: 'Java: rastreo (WebSocket)', build: () => ({
          steps: [
            T('jv', 'wsn', 'GET /ws/rastreo · Upgrade', 'req', 'El mapa de rastreo abre un WebSocket al puerto exclusivo 8090.', { hl: ['location /ws/'] }),
            T('wsn', 'track', 'GET /ws/rastreo · Upgrade', 'req', 'NGINX reenvía Upgrade y Connection al servidor de rastreo.'),
            T('track', 'wsn', '101 Switching Protocols', 'ws', 'Se acepta el cambio de protocolo.'),
            T('wsn', 'jv', '101 Switching Protocols', 'ws', 'Canal abierto.'),
            T('track', 'wsn', 'frame · posición', 'ws', 'El servidor empuja la posición del repartidor.'),
            T('wsn', 'jv', 'frame · posición', 'ws', 'El marcador se mueve en el mapa.'),
          ],
        }),
      },
      {
        name: 'Acceso directo: port forward', build: () => ({
          steps: [
            T('py', 'tcp', 'TCP SYN :15001', 'tcp', 'Un cliente que quiere hablar directo con libros usa el puerto reenviado.'),
            T('tcp', 'libros', 'TCP SYN :5001', 'tcp', 'NGINX stream abre la segunda conexión.'),
            T('py', 'tcp', 'bytes opacos', 'tcp', 'Datos sin interpretar.'),
            T('tcp', 'libros', 'bytes idénticos', 'tcp', 'Pasan tal cual: sin reglas HTTP, sin límites, sin reescritura.'),
            T('libros', 'tcp', 'bytes respuesta', 'tcp', 'La respuesta vuelve por el mismo camino.'),
            T('tcp', 'py', 'bytes respuesta', 'tcp', 'Entregada al cliente.'),
          ],
        }),
      },
      {
        name: 'Navegador: monolito', build: () => ({
          steps: [
            T('el', 'http', 'GET /library/', 'req', 'Cualquier navegador entra al sitio web del monolito.', { hl: ['location /   {'] }),
            T('http', 'mono', 'GET /library/ + X-Forwarded-*', 'req', 'Reverse proxy clásico hacia Node :3000 con cabeceras de origen.'),
            T('mono', 'http', '200 OK · HTML', 'res', 'La app responde.'),
            T('http', 'el', '200 OK · HTML', 'res', 'El navegador ve la página; nunca supo del puerto 3000.'),
          ],
        }),
      },
    ],
  };

  /* ===================================================================== */
  /* Comparativa                                                           */
  /* ===================================================================== */
  const COMPARE = {
    head: ['Tipo', 'Del lado de…', 'Quién sabe que existe', 'A quién oculta', 'Capa', 'Función principal', 'En este proyecto'],
    rows: [
      ['Proxy directo', 'El cliente', 'El cliente (lo configura)', 'A los clientes ante los servidores', 'L7 (+ túnel L4 con CONNECT)', 'Filtrar, cachear, auditar y salir a Internet', 'No se usa (ejemplo: Squid)'],
      ['Proxy inverso', 'El servidor', 'Solo el operador', 'A los servidores ante los clientes', 'L7', 'Terminar TLS, ocultar y proteger la app', '01_reverse_proxy.conf → monolito :3000'],
      ['API Gateway', 'El servidor (muchas APIs)', 'Los clientes lo usan sin saberlo', 'A los microservicios y sus puertos', 'L7 (API)', 'Enrutar por ruta, reescribir, limitar, centralizar', '01_reverse_proxy.conf → /api/*'],
      ['Balanceador', 'El servidor (réplicas)', 'Solo el operador', 'Cuántos servidores hay detrás', 'L4 o L7', 'Repartir carga y tolerar fallas', 'Ejemplo upstream (1 instancia por servicio hoy)'],
      ['Port forward', 'El servidor', 'El cliente usa otro puerto', 'El puerto interno real', 'L4 (TCP/UDP)', 'Reenviar bytes sin interpretar', '02_port_forward.conf → :15001/15004/15005'],
      ['Proxy WebSocket', 'El servidor', 'Solo el operador', 'El backend de tiempo real', 'L7 → conexión larga', 'Mantener canales bidireccionales', '03_websocket.conf → :8090'],
    ],
  };

  window.PROXY_DATA = { scenes: [forward, reverse, gateway, balancer, portfwd, websocket, all], COMPARE };
})();
