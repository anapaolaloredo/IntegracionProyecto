#!/usr/bin/env bash
# Crea un certificado AUTOFIRMADO para pruebas (valido 365 dias) y lo deja en /etc/nginx/ssl.
# Uso:  ./crear_certificado.sh <IP-o-dominio-de-la-instancia>
#   ./crear_certificado.sh 34.123.45.67
#   ./crear_certificado.sh biblioteca.ejemplo.com
# Para produccion usa un dominio real con Let's Encrypt (certbot --nginx) en lugar de este script.
# La llave privada (.key) NUNCA se sube a git (ver .gitignore).
set -euo pipefail

HOST="${1:?Uso: $0 <IP-o-dominio>}"
DESTINO="${2:-/etc/nginx/ssl}"

if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then SAN="IP:$HOST,DNS:localhost,IP:127.0.0.1"
else SAN="DNS:$HOST,DNS:localhost,IP:127.0.0.1"; fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout "$TMP/library.key" -out "$TMP/library.crt" \
  -subj "/CN=$HOST/O=Libreria UDEM (pruebas)" \
  -addext "subjectAltName=$SAN"

sudo mkdir -p "$DESTINO"
sudo install -m 644 "$TMP/library.crt" "$DESTINO/library.crt"
sudo install -m 600 "$TMP/library.key" "$DESTINO/library.key"
echo "Certificado creado en $DESTINO (library.crt / library.key) para: $SAN"
echo "Como es autofirmado, el cliente debe confiar en el (o usar curl -k en las pruebas)."
