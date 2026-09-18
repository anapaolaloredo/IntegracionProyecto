# Postfix local para el 2FA (apps/services/login)

Este microservicio NUNCA usa un proveedor SMTP externo (Gmail, SendGrid,
etc.). El correo del 2FA lo entrega Postfix, instalado y corriendo en la
misma instancia de GCP, y se queda dentro de la instancia (buzon local del
usuario del sistema operativo) — no sale a internet.

## Instalar y configurar (una sola vez, en la instancia GCP — Rocky/RHEL)

```bash
sudo dnf install -y postfix mailx
sudo postconf -e 'inet_interfaces = loopback-only'
sudo postconf -e 'mydestination = localhost.localdomain, localhost, $myhostname'
sudo systemctl enable --now postfix
```

`inet_interfaces = loopback-only` asegura que Postfix solo escucha en
`localhost` (nunca acepta conexiones desde fuera de la instancia).
`mydestination` hace que Postfix entregue localmente cualquier correo
dirigido a esos dominios, en vez de intentar relay externo.

## Configurar el microservicio

En `apps/services/login/.env`:

```
SMTP_HOST=localhost
SMTP_PORT=25
LOCAL_MAILBOX_USER=<usuario de Linux con el que hiciste SSH, ej. output de `whoami`>
```

## Verificar que la entrega local funciona

```bash
echo "prueba manual" | mail -s "Prueba Postfix" "$(whoami)@localhost"
mail   # lista el correo entrante; abre el mensaje "Prueba Postfix"
```

Si `mail` te muestra el mensaje que acabas de mandarte, Postfix está listo
para que `mail/sender.py` le entregue los códigos 2FA.
