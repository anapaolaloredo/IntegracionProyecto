#!/usr/bin/env bash
# Instala NGINX: monolito + API gateway de los microservicios en el puerto 80 (Rocky/RHEL/AlmaLinux). Ejecutar EN la instancia:
#   cd <repo>/deploy/nginx && ./instalar_nginx.sh
set -euo pipefail
cd "$(dirname "$0")"

sudo dnf install -y nginx
sudo cp library.conf /etc/nginx/conf.d/library.conf

# SELinux (activo por omisión en RHEL): sin esto NGINX no puede conectarse a Node y responde 502.
if command -v setsebool >/dev/null 2>&1; then sudo setsebool -P httpd_can_network_connect 1; fi

# nginx.conf de RHEL trae su propio server en el 80; si choca con default_server, nginx -t lo dira.
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

echo "Listo. Pruebas:  curl -I http://localhost/   (302 a /library/)   y   curl http://localhost/health/pedidos"
echo "Y desde fuera: http://<IP-externa>/  (el firewall debe permitir tcp:80)"
