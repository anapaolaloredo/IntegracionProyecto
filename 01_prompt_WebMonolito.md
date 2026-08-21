1. Desarrolla una aplicación web monolítica en Node.js dentro del directorio /apps/web-monolito01 que gestione una librería en línea mediante acceso directo a PostgreSQL. 

2. La solución deberá renderizar HTML del lado del servidor, administrar usuarios registrados, implementar CRUD del modelo normalizado (en todas las tablas), manejar imágenes y conservar definiciones de conceptos asociadas a cada libro.

3. Restricción arquitectónica: no se desarrollarán APIs REST, GraphQL, SOAP ni otros servicios. No se utilizará JSON o XML como formato de intercambio de datos. El archivo package.json existe únicamente porque npm lo requiere para administrar el proyecto Node.js.

4. Parte del hecho que todo libro debe de tener ISBN, título, autor, año de publicación, género, precio, stock, formato, imágenes y conceptos definidos por libro, identifica dependencias funcionales y multivaluadas.

5. Un libro puede tener varios autores.
6. Un libro puede pertenecer a varios géneros.
7. Un libro puede definir muchos conceptos y un mismo concepto puede aparecer en distintos
libros con definiciones diferentes.
8. Un libro puede tener varias imágenes.
9. Formato y categoría son catálogos independientes.
10. Debe existir como máximo un administrador.

11. Utiliza el patrón arquitectónico macro-arquitectura monolitica
12. Utiliza el patrón de diseño MVC (Modelo Vista Controlador) para la gui 
13. Aplica el enfoque de organización de código modular 
14. Utiliza el esquema de base datos de postgres del archivo 'data/library_schema.sql'
15. Crea un archivo readme.md con la lógica del sistema e incluye los pasos para ejecutar y desplegar el sistema en un sistema Linux Centos 10 Stream. Anexa también, la configuración de la base de datos de Postgres usando el usuario library_user con password:'666', con la base de datos library