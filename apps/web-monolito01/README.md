# Libreria en linea — App monolitica (Node.js + PostgreSQL)

Aplicacion web **monolitica** para la gestion de una libreria en linea.
Renderiza HTML del lado del servidor (SSR) con **EJS**, accede
directamente a **PostgreSQL** (sin ORM) y **no expone ninguna API**
(REST/GraphQL/SOAP). No se usa JSON ni XML como formato de intercambio
de datos; toda la comunicacion entre navegador y servidor ocurre via
formularios HTML (`GET`/`POST`, con `method-override` para simular
`PUT`/`DELETE`) y respuestas HTML.

El archivo `package.json` existe unicamente porque `npm` lo requiere
para administrar dependencias del proyecto Node.js.

---

## 1. Logica del sistema

### 1.1 Arquitectura

- **Macro-arquitectura:** monolito — un unico proceso Node.js/Express
  sirve tanto la logica de negocio como las vistas.
- **Patron de diseno (GUI):** MVC.
  - **Modelo** (`src/models/`): acceso a datos vía `pg`, cada modelo
    invoca las funciones PL/pgSQL (`fn_*`) definidas en
    `data/library_schema.sql`.
  - **Vista** (`src/views/`): plantillas EJS, sin logica de negocio.
  - **Controlador** (`src/controllers/`): orquesta modelo y vista,
    valida entradas de formularios.
- **Organizacion modular:** cada dominio (auth, libros, usuarios,
  catalogos) tiene su propio modelo, controlador y carpeta de rutas.
  Los catalogos simples (formatos, generos, autores, conceptos)
  comparten una fabrica de controlador/rutas (`catalogoController.js`,
  `catalogoRoutes.js`) para no duplicar codigo.

### 1.2 Modelo de datos y normalizacion (resumen)

El esquema completo, con el analisis de dependencias funcionales (FD)
y multivaluadas (MVD) que sustenta el diseno en 4FN, esta documentado
como comentario al inicio de `data/library_schema.sql`. En sintesis:

- `isbn -> titulo, anio_publicacion, precio, stock, id_formato`
- `id_autor -> nombre_autor`, `id_genero -> nombre_genero`,
  `id_formato -> nombre_formato`, `id_concepto -> nombre_concepto`
- `(id_libro, id_concepto) -> definicion` (la definicion depende del
  par libro-concepto, no solo del concepto — de ahi que
  `libro_concepto` sea una entidad asociativa con atributo propio y
  no una MVD pura)
- MVDs independientes entre si sobre `libro`: `isbn ->> id_autor`,
  `isbn ->> id_genero`, `isbn ->> id_imagen`

Al existir tres MVDs independientes sobre `libro` (autor, genero,
imagen), el modelo se descompuso en **4FN** usando tablas puente
separadas (`libro_autor`, `libro_genero`, `imagenes_libro`) en vez de
una sola tabla que combinara estos atributos multivaluados, lo que
generaria anomalias de redundancia tipo producto cartesiano.

Formato y genero son catalogos independientes entre si (formato es
1:N con libro; genero es N:M con libro).

### 1.3 Reglas de negocio implementadas

- **Un unico administrador en todo el sistema:** garantizado en dos
  capas — (a) indice unico parcial en PostgreSQL
  (`uq_usuarios_admin_unico`, `WHERE rol = 'admin'`) y (b) logica de
  aplicacion: el primer usuario que se registra se vuelve `admin`
  automaticamente; todos los siguientes se registran como `cliente`.
- **Una portada por libro como maximo:** indice unico parcial
  (`uq_imagenes_portada_unica`).
- **Control de acceso:** cualquier usuario autenticado puede navegar
  el catalogo y ver el detalle de libros; **solo el admin** puede
  crear/editar/eliminar libros, catalogos, imagenes, conceptos y
  gestionar usuarios (middlewares `requerirSesion` / `requerirAdmin`).
- **Autores y generos:** relacion N:M via tablas puente; el
  formulario de libro permite seleccionar varios de cada uno
  (`<select multiple>`).
- **Conceptos:** un libro puede definir varios conceptos, y un mismo
  concepto (del catalogo) puede tener una definicion distinta en cada
  libro donde se use.
- **Imagenes:** un libro puede tener varias; se suben como archivo
  (multipart/form-data, via `multer`) y se guardan en
  `public/uploads/`, referenciadas por URL relativa en la BD.

### 1.4 Estructura de carpetas

```
web-monolito01/
├── data/
│   └── library_schema.sql      # Esquema PostgreSQL + funciones CRUD PL/pgSQL
├── public/
│   ├── css/estilos.css
│   └── uploads/                # Imagenes subidas por el admin
├── src/
│   ├── app.js                  # Punto de entrada Express
│   ├── config/db.js            # Pool de conexion PostgreSQL
│   ├── controllers/            # Controladores (MVC)
│   ├── middlewares/            # auth.js (sesiones/roles), upload.js (multer)
│   ├── models/                 # Acceso a datos (invoca funciones fn_*)
│   ├── routes/                 # Definicion de rutas Express
│   └── views/                  # Plantillas EJS (SSR)
├── .env.example
└── package.json
```

---

## 2. Requisitos

- Node.js 18 LTS o superior y npm
- PostgreSQL 13+ (probado con PostgreSQL 16)
- Acceso a puerto 3000 (o el que se configure en `.env`)

---

## 3. Configuracion de PostgreSQL

Se usa el usuario `library_user` (password `666`) y la base de datos
`library`, tal como especifica el enunciado del proyecto.

```bash
sudo -u postgres psql -c "CREATE USER library_user WITH PASSWORD '666';"
sudo -u postgres psql -c "CREATE DATABASE library OWNER library_user;"
sudo -u postgres psql -d library -c "GRANT ALL PRIVILEGES ON DATABASE library TO library_user;"

# Cargar el esquema (tablas, indices y funciones PL/pgSQL)
PGPASSWORD=666 psql -h localhost -U library_user -d library -f data/library_schema.sql
```

> Nota de seguridad: la contrasena `666` es la solicitada para este
> entorno de practica/evaluacion. En un despliegue real, usa una
> contrasena fuerte y gestion de secretos (no versionar `.env`).

---

## 4. Ejecucion local (desarrollo)

```bash
cp .env.example .env
npm install
npm start
# La app queda disponible en http://localhost:3000
```

El primer usuario que se registre en `/auth/registro` queda como
**administrador** automaticamente.

---

## 5. Despliegue en Linux CentOS Stream 10 (produccion)

Los pasos siguen el flujo tipico de CentOS Stream 10 (basado en
`dnf`, `firewalld` y `systemd`).

### 5.1 Actualizar el sistema e instalar herramientas base

```bash
sudo dnf update -y
sudo dnf install -y git firewalld
sudo systemctl enable --now firewalld
```

### 5.2 Instalar Node.js 20 LTS (via NodeSource)

```bash
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs
node -v
npm -v
```

### 5.3 Instalar y configurar PostgreSQL

```bash
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb

# Habilitar autenticacion por password para conexiones locales/red:
# editar /var/lib/pgsql/data/pg_hba.conf y cambiar los metodos
# "ident"/"peer" a "md5" o "scram-sha-256" en las lineas host/local.
sudo sed -i 's/ident/md5/g; s/peer/md5/g' /var/lib/pgsql/data/pg_hba.conf

sudo systemctl enable --now postgresql
```

Crear el usuario y la base de datos de la aplicacion:

```bash
sudo -u postgres psql -c "CREATE USER library_user WITH PASSWORD '666';"
sudo -u postgres psql -c "CREATE DATABASE library OWNER library_user;"
sudo -u postgres psql -d library -c "GRANT ALL PRIVILEGES ON DATABASE library TO library_user;"
```

Cargar el esquema y las funciones CRUD:

```bash
PGPASSWORD=666 psql -h localhost -U library_user -d library \
  -f /opt/web-monolito01/data/library_schema.sql
```

### 5.4 Desplegar el codigo de la aplicacion

```bash
sudo mkdir -p /opt/web-monolito01
sudo chown $USER:$USER /opt/web-monolito01
# Copiar (o clonar) el proyecto dentro de /opt/web-monolito01
cd /opt/web-monolito01

cp .env.example .env
# Editar .env si el host/puerto/credenciales difieren de los valores
# por defecto (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD, PORT,
# SESSION_SECRET).

npm install --omit=dev
```

### 5.5 Ejecutar la aplicacion como servicio con systemd

Crear `/etc/systemd/system/web-monolito01.service`:

```ini
[Unit]
Description=Libreria en linea - app monolitica Node.js
After=network.target postgresql.service

[Service]
Type=simple
User=nodeapp
WorkingDirectory=/opt/web-monolito01
EnvironmentFile=/opt/web-monolito01/.env
ExecStart=/usr/bin/node src/app.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Usuario dedicado para correr la app (buena practica de seguridad)
sudo useradd -r -s /sbin/nologin nodeapp
sudo chown -R nodeapp:nodeapp /opt/web-monolito01

sudo systemctl daemon-reload
sudo systemctl enable --now web-monolito01
sudo systemctl status web-monolito01
```

### 5.6 Abrir el puerto en el firewall

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload
```

### 5.7 (Opcional) SELinux

CentOS Stream 10 trae SELinux activo por defecto. Si el servicio no
puede escribir en `public/uploads/` o enlazar el puerto:

```bash
# Permitir que Node se ligue al puerto configurado (si no es 3000/8080/etc.)
sudo semanage port -a -t http_port_t -p tcp 3000 2>/dev/null || \
sudo semanage port -m -t http_port_t -p tcp 3000

# Contexto correcto para el directorio de subida de imagenes
sudo semanage fcontext -a -t httpd_sys_rw_content_t "/opt/web-monolito01/public/uploads(/.*)?"
sudo restorecon -Rv /opt/web-monolito01/public/uploads
```

### 5.8 (Opcional) Proxy inverso con Nginx

```bash
sudo dnf install -y nginx
```

`/etc/nginx/conf.d/web-monolito01.conf`:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo systemctl enable --now nginx
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

---

## 6. Variables de entorno (`.env`)

| Variable         | Descripcion                              | Valor por defecto |
|------------------|-------------------------------------------|--------------------|
| `PGHOST`         | Host de PostgreSQL                        | `localhost`        |
| `PGPORT`         | Puerto de PostgreSQL                      | `5432`              |
| `PGDATABASE`     | Nombre de la base de datos                | `library`           |
| `PGUSER`         | Usuario de PostgreSQL                     | `library_user`      |
| `PGPASSWORD`     | Password del usuario                      | `666`               |
| `PORT`           | Puerto en el que escucha la app           | `3000`              |
| `SESSION_SECRET` | Clave para firmar la cookie de sesion     | (cambiar en prod)  |
| `NODE_ENV`       | `development` \| `production`             | `production`        |

---

## 7. Notas sobre la restriccion de "sin API"

- No existen rutas que devuelvan `application/json` ni `application/xml`.
- Todas las rutas responden vistas EJS renderizadas en el servidor.
- Las mutaciones (crear/actualizar/eliminar) se realizan con `<form>`
  HTML estandar; `PUT`/`DELETE` se simulan con `method-override`
  (`?_method=PUT`) porque los navegadores solo soportan `GET`/`POST`
  de forma nativa en formularios.
- La subida de imagenes usa `multipart/form-data` (estandar HTML),
  no un endpoint de subida tipo API.
