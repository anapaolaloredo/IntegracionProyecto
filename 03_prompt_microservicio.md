Escribe un microservicio en flask (no blueprint) con una conexión a la base de datos postgres para generar los endpoints necesarios para las operaciones CRUD de libros. Usa exclusivamente pysicopg. Depositalo en apps/services/soap

1. Usa como referencia el esquema de base de datos disponible en data/library_schema.sql y el diseño XML de /apps/services/soap/library.xml
2. El microservicio debe mostrar todos los libros, un libro, buscar por atributos, modificar, borrar y actualizar libros.
3. Toma en consideración el problema CORS ya que este microservicio será accedido mediante clientes fuera del dominio.
4. Los datos de la base de datos postgres son user: library_user, password: library666 y la base de datos: library. Utiliza estos datos de acceso en un archivo .env
5. Utiliza swagger para la documentación del microservicio
