#!/usr/bin/env bash
# Instala NGINX con 3 archivos de configuracion (Rocky/RHEL/AlmaLinux). Ejecutar EN la instancia:
#   cd <repo>/deploy/nginx && ./instalar_nginx.sh
#   1) conf.d/01_reverse_proxy.conf  reverse proxy HTTP :80 (monolito + API gateway)
#   2) stream.d/02_port_forward.conf port forward TCP (modulo stream)
#   3) conf.d/03_websocket.conf      WebSockets exclusivos :8090
set -euo pipefail
cd "$(dirname "$0")"

sudo dnf install -y nginx nginx-mod-stream   # el modulo stream es paquete aparte en RHEL

# HTTPS: si no hay certificado, crea uno autofirmado para la IP/dominio recibido (./instalar_nginx.sh <host>)
if [ ! -f /etc/nginx/ssl/library.crt ]; then ./crear_certificado.sh "${1:-localhost}"; fi
sudo cp conf.d/01_reverse_proxy.conf conf.d/03_websocket.conf /etc/nginx/conf.d/
sudo mkdir -p /etc/nginx/stream.d
sudo cp stream.d/02_port_forward.conf /etc/nginx/stream.d/

# El contexto stream va a nivel raiz de nginx.conf, fuera de http { }.
if ! grep -q 'stream.d' /etc/nginx/nginx.conf; then
  sudo sed -i '/^http *{/i stream {\n    include /etc/nginx/stream.d/*.conf;\n}\n' /etc/nginx/nginx.conf
fi

# SELinux: sin esto NGINX no puede conectarse a los servicios internos y responde 502.
if command -v setsebool >/dev/null 2>&1; then sudo setsebool -P httpd_can_network_connect 1; fi

sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

echo "Listo. Firewall: tcp:80, tcp:443, tcp:8090, tcp:8443, tcp:15001,15004,15005."
echo "  curl -I http://localhost/            (302 a /library/)"
echo "  curl http://localhost/api/books      (-> libros)"
echo "  curl http://localhost:15001/health   (port forward)"
echo "  curl -k https://localhost/api/books  (HTTPS con certificado autofirmado)"
