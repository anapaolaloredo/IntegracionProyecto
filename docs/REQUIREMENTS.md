# Requisitos del sistema — Librería en línea (Ejercicio Guiado 02)

## 1. Alcance

Aplicación web monolítica (Node.js + Express + EJS, renderizado server-side) para la gestión de
una librería en línea, con acceso directo a PostgreSQL mediante `pg` y consultas parametrizadas.
Sin APIs REST/GraphQL/SOAP ni intercambio de datos vía JSON/XML entre frontend y backend.

## 2. Actores

| Actor | Puede | No puede |
|---|---|---|
| Visitante | Acceder a login y registro; páginas públicas expresamente autorizadas | Consultar catálogo, ver conceptos, acceder a CRUD |
| Usuario registrado | Consultar catálogo, buscar por ISBN/título, ver detalle de libro y conceptos | Crear/editar/eliminar libros, catálogos o usuarios; administrar imágenes |
| Administrador (máx. 1) | CRUD completo de libros, autores, géneros, formatos, conceptos, imágenes y usuarios | Existir más de un Administrador en el sistema |

## 3. Requisitos funcionales

| ID | Requisito | Criterio de aceptación |
|---|---|---|
| RF-01 | El sistema permite el registro de nuevos usuarios | Un visitante puede crear una cuenta con usuario, correo y contraseña; la contraseña se guarda con hash |
| RF-02 | El sistema permite iniciar sesión | Un usuario registrado accede con credenciales válidas y obtiene una sesión activa |
| RF-03 | El sistema permite cerrar sesión | Al cerrar sesión, la sesión se invalida y se redirige a una página pública |
| RF-04 | Los usuarios autenticados pueden consultar el catálogo de libros | El catálogo se muestra paginado/listado con datos básicos de cada libro |
| RF-05 | El sistema permite buscar libros por ISBN y por título | Una búsqueda por ISBN exacto o por título parcial devuelve los libros coincidentes |
| RF-06 | El Administrador puede crear, consultar, actualizar y eliminar libros | Cada operación CRUD tiene formulario, validación server-side y confirmación de resultado |
| RF-07 | El Administrador puede crear, consultar, actualizar y eliminar autores | Igual que RF-06, aplicado a autores |
| RF-08 | El Administrador puede crear, consultar, actualizar y eliminar géneros/categorías | Igual que RF-06, aplicado a géneros |
| RF-09 | El Administrador puede crear, consultar, actualizar y eliminar formatos | Igual que RF-06, aplicado a formatos |
| RF-10 | El Administrador puede crear, consultar, actualizar y eliminar conceptos y sus definiciones | Un concepto puede asociarse a varios libros con una definición distinta en cada uno |
| RF-11 | Un libro puede asociarse a varios autores y a varios géneros | Al editar un libro es posible agregar/quitar autores y géneros sin duplicar registros |
| RF-12 | El sistema permite registrar conceptos y definiciones específicas por libro | La definición pertenece a la relación libro-concepto, no al concepto en general |
| RF-13 | El Administrador puede cargar, editar y eliminar imágenes de un libro | Se aceptan JPG, PNG y WebP vía `multipart/form-data`; el nombre de archivo lo genera el sistema |
| RF-14 | Una imagen de libro puede marcarse como portada | Como máximo una imagen por libro queda marcada como portada |
| RF-15 | El sistema controla stock y precio de cada libro | No se permite guardar stock negativo ni precio inválido (< 0) |
| RF-16 | El sistema restringe la administración a un único usuario Administrador | Un intento de crear un segundo Administrador es rechazado por la base de datos |
| RF-17 | El sistema autoriza cada ruta según el rol del usuario | Un usuario regular que intenta acceder a una ruta administrativa recibe acceso denegado controlado |

## 4. Requisitos no funcionales

| ID | Requisito | Criterio de aceptación |
|---|---|---|
| RNF-01 | Seguridad | Contraseñas con hash, sesiones seguras, SQL parametrizado, `.env` fuera del control de versiones |
| RNF-02 | Mantenibilidad | Separación de responsabilidades (rutas, controladores/servicios, modelos, vistas, middleware) |
| RNF-03 | Integridad de datos | Esquema normalizado hasta 4FN con PK, FK, UNIQUE y CHECK en PostgreSQL |
| RNF-04 | Rendimiento básico | Búsquedas por ISBN/título e índices en columnas de filtrado frecuente |
| RNF-05 | Usabilidad | Formularios con validación visible y mensajes de error/éxito claros |
| RNF-06 | Disponibilidad | La aplicación responde de forma consistente detrás del reverse proxy (`/library`) |
| RNF-07 | Trazabilidad de errores | Los errores se registran en servidor sin exponer detalles internos ni SQL al usuario final |
| RNF-08 | Facilidad de despliegue | Scripts SQL numerados y ejecutables en orden reproducible sobre una instancia nueva |

## 5. Supuestos

- El primer usuario registrado en el sistema se designa automáticamente como Administrador.
- "Género" y "categoría" se tratan como el mismo catálogo (`generos`) en este dominio.
- Se opera con un único servidor (sin balanceo de carga ni réplicas).
- Las imágenes se almacenan en el sistema de archivos del servidor (`uploads/`), no en un servicio externo.

## 6. Restricciones

- No se desarrollarán APIs REST, GraphQL, SOAP ni microservicios.
- No se usará JSON ni XML como mecanismo de intercambio entre frontend y backend.
- Debe existir como máximo un Administrador, reforzado también a nivel de base de datos.
- Node.js debe escuchar únicamente en `127.0.0.1:3000`; la exposición pública es vía Apache/NGINX.
- Las contraseñas y el archivo `.env` nunca se publican ni se suben al control de versiones.

## 7. Riesgos identificados

| Riesgo | Mitigación prevista |
|---|---|
| Acceso no autorizado a rutas administrativas | Middleware de autenticación + autorización por rol |
| SQL Injection | Consultas parametrizadas con `pg`, nunca concatenación de strings |
| Subida de archivos peligrosos | Validación de extensión/MIME/tamaño; nombre de archivo generado por el sistema |
| Exposición de credenciales | Variables de entorno (`.env`), excluidas del repositorio y del `.tar.gz` de entrega |
| Eliminación accidental de información | Restricciones `ON DELETE` explícitas y confirmaciones en la interfaz |
| Publicación de datos sensibles | Revisión previa a publicar en `ubiquitous.udem.edu` (sin contraseñas, tokens ni `.env`) |