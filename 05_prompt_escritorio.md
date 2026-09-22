Objetivo: Desarrollar una aplicación de escritorio en Python que funcione como cliente de los microservicios de autenticación y gestión de libros desarrollados durante el curso.

Desarrolle una aplicación gráfica utilizando Python 3.10 o superior. Puede utilizar PySide6, Tkinter u otra biblioteca para interfaces gráficas que considere apropiada. La aplicación deberá ejecutarse como una aplicación independiente y comunicarse con los microservicios mediante HTTP.

1. Autenticacion: deberá permitir

-Registrar un nuevo usuario.
-Iniciar sesión mediante correo electrónico y contraseña.
-Detectar credenciales incorrectas.
-Detectar cuentas que todavía no puedan autenticarse.
-Mostrar mensajes comprensibles ante errores del servicio.
-Mantener la información necesaria de la sesión iniciada.

La aplicación deberá utilizar, según corresponda, los servicios:

POST /register 
GET /verify
POST /login 
POST /logout
GET /session
POST /session/extend
PATCH /profile

Si falta algun endpoint, ayudame a completarlo. session extend no estoy segura de que este 

Asegurate de que las sesiones se mantengan guardadas 
Sin embargo, recuerde que: recordar localmente a un usuario no significa que la sesión del servidor continúe siendo válida.



2. Panel principal 

Tras el inicio de sesión, 

Panel principal

Después de una autenticación correcta deberá mostrarse un panel principal desde el cual puedan accederse las diferentes funciones de la aplicación. El diseño visual queda a criterio del estudiante, pero deberá existir una separación clara entre:

Sesión y perfil.
Catálogo de libros.
Administración de libros.
Estado de los servicios.
Configuración del servidor.
La aplicación deberá ser funcional y usable en Windows 11.

3. Estado de los microservicios

El panel principal deberá mostrar visualmente el estado de:

Microservicio de Login

Microservicio de Libros

Utilice el endpoint /health correspondiente.

La aplicación deberá diferenciar al menos tres estados:

🟢 Servicio funcionando correctamente y con acceso a su base de datos.
🟡 Servicio accesible, pero con alguna dependencia degradada o base de datos no disponible.
🔴 Servicio inaccesible, con error de conexión o sin respuesta.
Deberá mostrarse también la fecha y hora de la última comprobación. Incluya una forma de realizar nuevamente la comprobación sin reiniciar la aplicación. Además, la aplicación deberá realizar comprobaciones periódicas mientras se encuentra en ejecución.

4. Prueba obligatoria de tolerancia a fallos

Durante las pruebas deberá provocar deliberadamente al menos las siguientes situaciones:

Caso A: ambos microservicios disponibles.
Caso B: detener el microservicio de libros mientras la aplicación continúa ejecutándose.
Caso C: restaurar el microservicio de libros.
Caso D: intentar utilizar una URL o puerto incorrecto.
La aplicación no deberá cerrarse inesperadamente en ninguno de estos casos. Documente qué ocurrió y cómo reaccionó su aplicación.

5. Perfil del usuario

El usuario autenticado deberá poder consultar la información asociada con su sesión y modificar los datos permitidos por el microservicio. Deberá ser posible trabajar, según las capacidades actuales del servicio, con:

Nombre.
Apellidos.
Correo electrónico.
Contraseña.
También deberá implementarse la extensión de sesión. Cuando sea posible determinar que una sesión está próxima a expirar, la interfaz deberá advertir al usuario. No se solicita implementar un CRUD administrativo completo de usuarios debido a que el microservicio actual no proporciona todos los endpoints necesarios para ello.

6. Catálogo de libros

Implemente una sección visual para consultar el catálogo remoto. La información deberá obtenerse mediante el microservicio de libros y no mediante acceso directo a su base de datos. Considere: GET /books?format=json  Cada libro deberá visualizarse de forma organizada mostrando la información disponible, incluyendo:

ISBN.
Título.
Autor o autores.
Género.
Año.
Precio.
Existencia.
Formato.
Categoría.
Imagen.
Cuando existan varias imágenes, el usuario deberá poder consultarlas. Cuando un libro no tenga imagen, la aplicación deberá indicarlo visualmente sin provocar errores.

7. Búsqueda de libros

El usuario deberá poder localizar libros utilizando diferentes criterios. Como mínimo deberán considerarse búsquedas o filtros relacionados con:

ISBN.
Título.
Año.
Precio mínimo.
Precio máximo.
Al seleccionar un libro deberá consultarse su información detallada utilizando: GET /books/{isbn}  El detalle deberá incluir también los conceptos o definiciones que el microservicio tenga asociados al libro.

8. CRUD de libros

La aplicación deberá demostrar el consumo de los siguientes métodos HTTP:

GET
POST
PUT
PATCH
DELETE
Para ello deberá utilizar los endpoints disponibles:

GET /books
GET /books/{isbn}
POST /books
PUT /books/{isbn}
PATCH /books/{isbn}
DELETE /books/{isbn}
La interfaz deberá permitir realizar las operaciones necesarias sobre los libros. No se considerará suficiente que los botones aparezcan en pantalla: las operaciones deberán comprobarse contra el microservicio remoto y reflejarse posteriormente en el catálogo. Antes de eliminar información deberá solicitarse confirmación al usuario.

9. Diferencia entre PUT y PATCH

Su implementación deberá demostrar que comprende que PUT y PATCH no representan necesariamente la misma operación. Durante la demostración deberá mostrar:

Una actualización completa de un libro.
Una actualización parcial modificando únicamente un atributo.
Deberá explicar brevemente qué información fue enviada al servidor en cada caso y por qué utilizó PUT o PATCH.

11. Manejo de respuestas HTTP

La aplicación deberá interpretar apropiadamente las respuestas recibidas. Durante las pruebas deberán mostrarse ejemplos reales de al menos:

Una operación correcta.
Credenciales incorrectas.
ISBN duplicado.
Libro inexistente.
Servicio no disponible.
Sesión expirada o no válida.
Los mensajes presentados al usuario deberán ser comprensibles. No se deberá mostrar únicamente un traceback de Python como respuesta a un error.

12. Configuración del servidor

La aplicación deberá permitir modificar las direcciones utilizadas para conectarse a los servicios sin cambiar manualmente el código fuente. Deberá existir una pantalla de configuración donde puedan establecerse los datos necesarios para conectarse a los microservicios. La configuración deberá:

Poder modificarse.
Poder probarse.
Poder guardarse.
Persistir después de cerrar la aplicación.
Permitir restaurar los valores predeterminados.
La solución deberá funcionar tanto con servicios ejecutándose localmente como con los servicios desplegados en la infraestructura utilizada durante el curso. Por ejemplo, durante desarrollo podrán utilizarse:

http://localhost:5000

http://localhost:5001

Pera el ejercicios deberá estar en una instancia y la aplicación deberá construir correctamente las direcciones utilizadas en las peticiones.

