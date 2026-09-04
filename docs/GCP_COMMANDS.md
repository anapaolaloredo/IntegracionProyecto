# Comandos de infraestructura — GCP SDK CLI

Todos los comandos se ejecutaron con Google Cloud SDK CLI (`gcloud`) desde una estación local ya
autenticada. No se incluyen llaves privadas, tokens ni credenciales en este documento.

## 1. Autenticación y verificación del proyecto

```bash
gcloud --version
gcloud auth list
gcloud projects list          # una vez autenticada la cuenta
gcloud organizations list
```

## 2. Creación / gestión de proyectos (ejercicio de práctica)

```bash
gcloud projects create proyecto-01-11082026 --name="Proyectos de pruebas del grupo 03"
gcloud projects delete PROJECT_ID    # borra un proyecto
```

## 3. Creación de la instancia de Compute Engine

Instancia usada para este ejercicio (`web-monolito01` + PostgreSQL en el mismo servidor):

```bash
gcloud compute instances create maquina-integracion \
  --machine-type=e2-standard-2 \
  --image-family=centos-stream-10 \
  --image-project=centos-cloud \
  --boot-disk-size=50GB \
  --zone=southamerica-south1-c
```

También se creó una instancia equivalente para pruebas del grupo (`maquina-03`), con la misma
configuración:

```bash
gcloud compute instances create maquina-03 \
  --machine-type=e2-standard-2 \
  --image-family=centos-stream-10 \
  --image-project=centos-cloud \
  --boot-disk-size=50GB \
  --zone=southamerica-south1-c
```

> **Nota de corrección:** en el borrador original estas líneas tenían banderas partidas con
> guiones sueltos (`-- machine-type=... - -image-family=...`), un artefacto de copiar/pegar desde
> un procesador de texto. La forma válida para `gcloud` usa `--flag=valor` pegado, como arriba.

### Justificación del dimensionamiento

| Parámetro | Valor | Justificación |
|---|---|---|
| Tipo de máquina | `e2-standard-2` | 2 vCPU y 8 GB de RAM: suficiente para correr en el mismo servidor Node.js (proceso único, sin clustering) **y** PostgreSQL con un volumen de datos de práctica (decenas de filas por tabla), sin necesidad de separar la base de datos en otra instancia para un ejercicio académico. |
| Imagen | `centos-stream-10` (proyecto `centos-cloud`) | Requisito explícito del ejercicio (CentOS Stream 10); confirmado en el servidor real por el kernel `6.12.0-233.el10.x86_64`. |
| Disco de arranque | 50 GB | Margen suficiente para el sistema operativo, PostgreSQL, Node.js/`node_modules`, y las imágenes subidas por la aplicación (`public/uploads/`), sin acercarse al límite en un entorno de práctica. |
| Zona | `southamerica-south1-c` | Región más cercana disponible para el equipo, minimizando latencia de acceso desde México/Sudamérica durante el desarrollo y las pruebas. |

**Riesgo/limitación:** `e2-standard-2` con PostgreSQL y Node.js compartiendo la misma instancia es
adecuado para un ejercicio, pero no aísla el consumo de recursos entre la base de datos y la
aplicación — un pico de tráfico o una consulta pesada podría degradar ambos servicios a la vez. En
un entorno productivo real se separaría la base de datos (por ejemplo, Cloud SQL) de la capa de
aplicación.

## 4. Acceso a la instancia

```bash
gcloud compute ssh user@maquina-integracion
```

## 5. Reglas de firewall

```bash
# HTTP (80) — para el reverse proxy NGINX público (ver configuración real en la sección 7.1)
gcloud compute firewall-rules create allow-http \
  --network=default \
  --source-ranges=0.0.0.0/0 \
  --allow tcp:80

# Puerto de Node.js (3000) — sólo se usó para probar la app antes de poner
# el reverse proxy delante; en producción Node únicamente escucha en
# 127.0.0.1 y este puerto no debería quedar expuesto a 0.0.0.0/0.
gcloud compute firewall-rules create web-monolito01 \
  --network=default \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:3000 \
  --source-ranges=0.0.0.0/0
```

> **Riesgo identificado:** la regla `web-monolito01` deja el puerto 3000 abierto a cualquier IP
> (`0.0.0.0/0`). Como Node ya está configurado para escuchar sólo en `127.0.0.1:3000` (ver
> `PORT`/`app.listen` en `app.js`), el puerto no es alcanzable aunque la regla exista, pero lo
> correcto para producción es eliminar esta regla una vez confirmado que el reverse proxy funciona,
> dejando sólo el puerto 80 (o 443) abierto públicamente.

## 6. Instalación de PostgreSQL en la misma instancia

```bash
sudo dnf -y install postgresql-server
su - postgres
psql -c "\c library library_user"
```

## 7. Preparación del entorno y despliegue del código

```bash
sudo mkdir udem
sudo chown $USER:$USER udem -R

sudo dnf install git -y
cd /etc/yum.repos.d/
sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install gh --repo gh-cli

ssh-keygen -t ed25519 -C "ana.loredo@udem.edu"
more ~/.ssh/id_ed25519.pub          # agregar la llave pública a GitHub

git clone git@github.com:anapaolaloredo/IntegracionProyecto.git
cd IntegracionProyecto
git pull

sudo dnf install npm -y
```

## 7.1. Configuración real del reverse proxy (NGINX)

El reverse proxy usado es **NGINX**, no Apache. Configuración real usada en el servidor
(`/etc/nginx/conf.d/`, o el bloque `server` correspondiente):

```nginx
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3000;

        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Por qué `location /` y no `location /library`:** este bloque reenvía **todo** lo que llega al
puerto 80 hacia `127.0.0.1:3000` sin reescribir la ruta (no hay una barra final en `proxy_pass`,
así que NGINX conserva la URI completa tal cual, incluyendo el prefijo `/library`). Es justo el
comportamiento que necesita esta app: como el código usa `BASE_PATH=/library` para montar sus
propias rutas (ver sección 12 del reporte técnico), NGINX no necesita saber nada sobre `/library`
— sólo reenvía, y es Node quien reconoce el prefijo. Si NGINX reescribiera la ruta (por ejemplo,
con `location /library/ { proxy_pass http://127.0.0.1:3000/; }`, con barra final), le quitaría el
prefijo a la petición antes de que Node la viera, y todo el trabajo de `BASE_PATH` dejaría de
tener efecto.

Comandos típicos para aplicar este archivo (ajustar la ruta exacta según cómo se haya guardado):

```bash
sudo nginx -t                 # valida la sintaxis antes de recargar
sudo systemctl reload nginx
```

## 7.2. Resolución de problemas reales durante el primer despliegue (con NGINX ya proxyando)

Con NGINX ya configurado como arriba, el primer `npm start` en el servidor falló varias veces
seguidas. Los tres problemas reales y sus comandos de solución, en el orden en que aparecieron:

**a) `git pull` fallaba con "untracked files would be overwritten by merge"**

`node_modules/` generado localmente en el servidor chocaba con archivos que el commit remoto
también tocaba. Solución (verificando primero que no hubiera trabajo propio sin commitear):

```bash
git status
rm -rf apps/web-monolito01/node_modules   # regenerable, no es código propio
git pull
cd apps/web-monolito01 && npm install
```

**b) `EACCES: permission denied` al reconstruir `bcrypt`**

Parte de `node_modules` había quedado con dueño distinto al usuario que corre la app (instalación
previa como otro usuario/root). Solución:

```bash
ls -ld /opt/udem/IntegracionProyecto
sudo chown -R anapaolaloredomoreno:anapaolaloredomoreno /opt/udem/IntegracionProyecto
rm -rf node_modules
npm install
```

**c) `bcrypt`: "invalid ELF header" al arrancar con `npm start`**

Binario nativo (`.node`) incompatible con la arquitectura/SO del servidor (agravado por el
`rm -rf` parcial del paso anterior). El servidor es RHEL/AlmaLinux/Rocky 10 (`el10`), sin
herramientas de compilación instaladas por defecto:

```bash
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y python3
npm rebuild bcrypt --build-from-source
npm start
```

> Estos tres comandos resolvieron por completo el arranque de la aplicación Node.js detrás de
> NGINX. La configuración de NGINX en sí ya está documentada arriba (sección 7.1).

## 8. Carga del esquema y arranque de la aplicación

```bash
psql -U library_user -d library -f library_schema.sql
# alternativa usada cuando el rol library_user no tenía permisos suficientes:
sudo -u postgres psql -d library -f library_schema.sql

# Triggers y vistas (agregados el 2026-08-31; deben cargarse DESPUÉS del
# esquema porque usan sus tablas, y ANTES del seed):
psql -U library_user -d library -f library_triggers.sql
psql -U library_user -d library -f library_views.sql
psql -U library_user -d library -f library_data.sql

npm start
```

## 9. Gestión del ciclo de vida de la instancia

```bash
gcloud compute instances list
gcloud compute instances stop maquina-integracion
gcloud compute instances start maquina-integracion
```

## Resuelto el 2026-09-01

- ✅ Scripts reorganizados al esquema `db/00_create_database.sql` … `db/06_views.sql` que pide el
  ejercicio (antes eran `data/library_*.sql` sueltos). Verificados uno por uno cargando en orden
  (`00→01→04→05→06→02`) contra una base de datos recién creada — ver `docs/TEST_PLAN.md`.
- ✅ Seed ampliado a 30 filas por tabla (`db/02_seed_30_per_table.sql`); `formatos` se quedó en 8
  por decisión documentada (`docs/ENGINEERING_DECISIONS.md`, D-18).

## Lo único que sigue pendiente (requiere acceso directo al servidor real de GCP)

Esto **no se puede resolver desde aquí** — necesita que alguien con acceso a `maquina-integracion`
lo ejecute y confirme:

- Confirmar que `library_triggers.sql` y `library_views.sql` (o sus equivalentes `db/05`/`db/06`)
  ya están cargados en el servidor real, no sólo en la BD local de prueba — la app en producción
  depende de `vista_catalogo_libros` para el catálogo (`LibroModel.listarConDetalle`); si esa vista
  no existe ahí, `/library/libros` falla con `500` aunque en local funcione perfecto.
- Verificar con `\du library_user` en el servidor real (no sólo local) que el rol no es
  superusuario — ver `docs/SECURITY_REVIEW.md`, control #9.
- Capturas de pantalla reales (no texto) de `psql` mostrando funciones, triggers, vistas y conteos
  ejecutados directamente en `maquina-integracion`, para el punto 10 del ejercicio.
