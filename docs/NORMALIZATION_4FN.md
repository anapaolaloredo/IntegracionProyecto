# Normalización hasta 4FN — Librería en línea (Ejercicio Guiado 02)

Este documento reconstruye la evolución **1FN → 2FN → 3FN/BCNF → 4FN** que lleva al esquema final
implementado en `data/library_schema.sql`. No se presenta sólo el modelo final: en cada paso se
muestra la violación concreta (con datos reales tomados de la base de datos de prueba de este
proyecto), la anomalía que produce, y la descomposición que la resuelve.

**Ejemplo que se usa en todo el documento:** el libro *Cien años de soledad* (ISBN
`9780307474728`), que en la base de datos de prueba tiene 3 autores (Gabriel García Márquez,
Isabel Allende, Jorge Luis Borges), 3 géneros (Realismo mágico, Ciencia ficción, Fantasía), 1
imagen y 1 concepto definido. Es el caso real más "cargado" del seed y por eso es el que mejor
expone las anomalías de un diseño no normalizado.

## Punto de partida: estructura sin normalizar (UNF)

Antes de modelar la base de datos, la información de un libro podría llevarse en una sola hoja de
cálculo, con una fila por libro y columnas que agrupan varios valores:

| isbn | titulo | anio | precio | stock | formato | autores (grupo repetitivo) | generos (grupo repetitivo) | imagenes (grupo repetitivo: url, orden, portada) | conceptos (grupo repetitivo: nombre + definición) |
|---|---|---|---|---|---|---|---|---|---|
| 9780307474728 | Cien años de soledad | 1967 | 299.99 | 12 | Tapa dura | García Márquez, Allende, Borges | Realismo mágico, Ciencia ficción, Fantasía | (openlibrary.org/...L.jpg, 0, portada) | (Realismo mágico (recurso literario), "Definicion para el libro 1") |

Esto **no está en 1FN**: cuatro columnas (`autores`, `generos`, `imagenes`, `conceptos`) contienen
grupos repetitivos/listas dentro de una sola celda, en vez de valores atómicos.

## Dependencias identificadas (documentadas también como comentario en `data/library_schema.sql`)

**Dependencias funcionales (FD):**

```
isbn -> titulo, anio_publicacion, precio, stock, id_formato
id_autor -> nombre_autor
id_genero -> nombre_genero
id_formato -> nombre_formato
id_concepto -> nombre_concepto
(id_libro, id_concepto) -> definicion
```

**Dependencias multivaluadas (MVD), independientes entre sí sobre el libro:**

```
isbn ->> id_autor    (un libro tiene varios autores, sin relación con sus géneros o imágenes)
isbn ->> id_genero   (un libro tiene varios géneros, sin relación con sus autores o imágenes)
isbn ->> id_imagen   (un libro tiene varias imágenes, sin relación con autores o géneros)
```

## Paso 1 — Primera Forma Normal (1FN)

**Regla:** todo atributo debe contener un único valor atómico; no se permiten grupos repetitivos
ni valores multivaluados en una misma celda.

**Violación en el punto de partida:** `autores`, `generos`, `imagenes` y `conceptos` son columnas
con listas.

**Anomalía si no se corrige:** no se puede escribir `WHERE autor = 'Isabel Allende'` de forma
confiable (habría que hacer *pattern matching* sobre texto libre), no se puede garantizar que un
`id_autor` sea el mismo valor cada vez que se escribe su nombre (typos → "Isabel Allende" vs
"I. Allende" tratados como personas distintas), y agregar un cuarto autor obliga a reescribir toda
la celda.

**Corrección (1FN):** aplanar el grupo repetitivo repitiendo el resto de las columnas por cada
combinación. Con 3 autores × 3 géneros × 1 imagen × 1 concepto para este libro, la tabla plana en
1FN se ve así (9 filas para un solo libro):

| isbn | titulo | anio | precio | stock | formato | autor | genero | url_imagen | concepto | definicion |
|---|---|---|---|---|---|---|---|---|---|---|
| 9780307474728 | Cien años de soledad | 1967 | 299.99 | 12 | Tapa dura | García Márquez | Realismo mágico | .../L.jpg | Realismo mágico (recurso literario) | Definicion para el libro 1 |
| 9780307474728 | Cien años de soledad | 1967 | 299.99 | 12 | Tapa dura | García Márquez | Ciencia ficción | .../L.jpg | Realismo mágico (recurso literario) | Definicion para el libro 1 |
| 9780307474728 | Cien años de soledad | 1967 | 299.99 | 12 | Tapa dura | García Márquez | Fantasía | .../L.jpg | Realismo mágico (recurso literario) | Definicion para el libro 1 |
| 9780307474728 | Cien años de soledad | 1967 | 299.99 | 12 | Tapa dura | Allende | Realismo mágico | .../L.jpg | Realismo mágico (recurso literario) | Definicion para el libro 1 |
| 9780307474728 | Cien años de soledad | 1967 | 299.99 | 12 | Tapa dura | Allende | Ciencia ficción | .../L.jpg | Realismo mágico (recurso literario) | Definicion para el libro 1 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| *(9 filas en total: 3 autores × 3 géneros, repitiendo imagen y concepto)* |

**Ya en 1FN, pero con un problema evidente:** el precio, el stock, el título y hasta la
`url_imagen` y el `concepto` se repiten 9 veces para el mismo libro. Cambiar el precio requeriría
actualizar 9 filas (anomalía de actualización); borrar por error la única fila con
`autor = 'Borges'` no debería borrar el libro completo, pero en una tabla plana así es fácil que
un `DELETE` mal filtrado sí lo haga (anomalía de eliminación); y no se puede registrar un libro
nuevo sin al menos un autor y un género, porque no hay dónde poner el libro sin esas columnas
(anomalía de inserción).

## Paso 2 — Segunda Forma Normal (2FN)

**Regla:** además de estar en 1FN, todo atributo no clave debe depender de **toda** la clave
candidata, no sólo de una parte de ella.

**Clave candidata de la tabla plana en 1FN:** `(isbn, autor, genero)` como mínimo (con `imagen` y
`concepto` también podría ampliarse, pero ya con `isbn+autor+genero` se identifica una fila).

**Violación:** `titulo`, `anio`, `precio`, `stock` y `formato` dependen **únicamente de `isbn`**,
no de la clave completa `(isbn, autor, genero)` — son dependencias parciales.

**Anomalía si no se corrige:** exactamente las mismas de arriba (actualización/eliminación/inserción),
porque el atributo `precio` "no le pertenece" a la combinación autor-género, le pertenece sólo al
libro.

**Corrección (2FN):** separar los atributos que dependen sólo de `isbn` en su propia relación:

```
LIBROS(isbn PK, titulo, anio_publicacion, precio, stock, formato)
LIBRO_AUTOR_GENERO(isbn FK, autor, genero, url_imagen, concepto, definicion)
```

Con esto, `precio` vive una sola vez por libro. Pero `LIBRO_AUTOR_GENERO` sigue mezclando cuatro
hechos independientes (autor, género, imagen, concepto) en una sola tabla — eso todavía no es
correcto, y se resuelve en los pasos siguientes.

## Paso 3 — Tercera Forma Normal / BCNF

**Regla (BCNF):** para toda dependencia funcional no trivial `X -> Y`, `X` debe ser una clave
candidata de la relación donde vive.

**Violación:** dentro de `LIBROS(isbn, titulo, anio, precio, stock, formato)`, el atributo
`formato` es en realidad un nombre de catálogo (`nombre_formato`) que **no depende de `isbn`**
como un dato propio del libro, sino que es un valor que se repite igual para todos los libros de
ese formato (Tapa dura/Tapa blanda/Digital). Guardarlo como texto libre en cada fila de `LIBROS`
permite inconsistencias (`"Tapa Dura"` vs `"tapa dura"` vs `"Tapadura"` para el mismo formato en
libros distintos) y no permite editar el nombre de un formato en un solo lugar. Lo mismo aplica a
`autor`, `genero` y `concepto` en la tabla intermedia del paso anterior: son entidades con
identidad propia, no atributos del libro.

**Anomalía si no se corrige:** renombrar "Tapa dura" a "Pasta dura" exigiría un `UPDATE` masivo
sobre todos los libros con ese formato en vez de una sola fila; un typo en el nombre de un autor
en un libro no se refleja en sus otros libros (inconsistencia), y no hay forma de listar "todos los
autores" sin escanear y deduplicar la tabla de libros.

**Corrección (BCNF):** extraer cada catálogo a su propia relación, con una clave subrogada
(`SERIAL`) como determinante:

```
FORMATOS(id_formato PK, nombre_formato)
AUTORES(id_autor PK, nombre_autor)
GENEROS(id_genero PK, nombre_genero)
CONCEPTOS(id_concepto PK, nombre_concepto)
LIBROS(id_libro PK, isbn, titulo, anio_publicacion, precio, stock, id_formato FK)
```

En cada una de estas relaciones, la única dependencia funcional no trivial es `id_X -> nombre_X`
(o `isbn/titulo/... -> id_libro` para libros), y en ambos casos el determinante **es** la clave —
por lo tanto ya cumplen BCNF. Esto corresponde exactamente a las tablas `formatos`, `autores`,
`generos`, `conceptos` y `libros` de `data/library_schema.sql`.

**Lo que todavía falta:** cómo conectar `libros` con `autores`, `generos`, `imagenes` y
`conceptos` sin volver a caer en una tabla plana como la del paso 2. Eso es exactamente lo que
resuelve la 4FN.

## Paso 4 — Cuarta Forma Normal (4FN)

**Regla:** además de BCNF, no debe existir una dependencia multivaluada no trivial `X ->> Y` a
menos que `X` sea una superclave. Cuando un mismo determinante tiene **varias** dependencias
multivaluadas independientes entre sí, cada una debe vivir en su propia relación.

**Violación (la "trampa de conexión"):** si se intentara mantener autores, géneros e imágenes de
un libro en una sola tabla puente —por ejemplo
`LIBRO_DETALLE(id_libro, id_autor, id_genero, id_imagen)`— para *Cien años de soledad* (3 autores,
3 géneros, 1 imagen) esa tabla necesitaría **9 filas** (3×3×1) sólo para representar que el libro
tiene esos 3 autores y esos 3 géneros, aunque autor y género **no tienen ninguna relación entre
sí** (no existe el concepto de "el género que corresponde a tal autor en tal libro"). Esto es
precisamente lo que la teoría relacional llama *connection trap*: agregar un cuarto autor
obligaría a agregar 3 filas más (una por cada género ya existente) sólo para mantener la tabla
consistente, cuando en realidad sólo se agregó un hecho nuevo.

**Anomalía si no se corrige:** insertar un autor nuevo exige conocer y repetir todos los géneros
ya asociados (anomalía de inserción); borrar por error una fila de esa tabla puede eliminar la
única constancia de una asociación autor-libro sin querer tocar los géneros, o viceversa
(anomalía de eliminación); y el conteo de "cuántos autores tiene el libro" requeriría hacer
`DISTINCT` sobre una tabla inflada artificialmente (redundancia).

**Corrección (4FN):** cada dependencia multivaluada independiente se separa en su propia relación
binaria, con `isbn`/`id_libro` como parte de la clave en cada una, pero **sin cruzarlas entre sí**:

```
LIBRO_AUTOR(id_libro FK, id_autor FK)         PK (id_libro, id_autor)     -- resuelve isbn ->> id_autor
LIBRO_GENERO(id_libro FK, id_genero FK)       PK (id_libro, id_genero)    -- resuelve isbn ->> id_genero
IMAGENES_LIBRO(id_imagen PK, id_libro FK, url_imagen, orden, es_portada)  -- resuelve isbn ->> id_imagen
```

Con esta descomposición, *Cien años de soledad* queda representado con **3 filas** en
`libro_autor`, **3 filas** en `libro_genero` y **1 fila** en `imagenes_libro` — cada hecho
independiente en su propia tabla, sin producto cartesiano artificial. Esto es exactamente lo que
implementa `data/library_schema.sql` y lo que se verificó con datos reales en `docs/TEST_PLAN.md`
(TC-10: se asociaron autores y géneros adicionales al libro 1 y `fn_listar_autores_por_libro`/
`fn_listar_generos_por_libro` devolvieron cada conjunto sin ningún cruce entre sí).

### Caso especial: `libro_concepto` — por qué NO es una MVD pura

A primera vista, `isbn ->> id_concepto` (un libro puede tener varios conceptos) parece ser una
cuarta dependencia multivaluada independiente, tratable igual que autor/género/imagen. **No lo
es**, y tratarla como tal sería un error de diseño:

- Si fuera una MVD pura, la *definición* de "Realismo mágico" tendría que ser la misma sin importar
  en qué libro aparezca (igual que el `nombre_autor` es el mismo sin importar en qué libro
  aparezca ese autor).
- Pero el propio requisito del ejercicio (y la evidencia en `docs/TEST_PLAN.md`, TC-11) dice lo
  contrario: **el mismo concepto puede tener una definición distinta según el libro** — se probó
  exactamente eso: `fn_definir_concepto(1, 1, 'Definicion para el libro 1')` y
  `fn_definir_concepto(2, 1, 'Definicion distinta para el libro 2')` conviven sin conflicto.
- Eso significa que existe una dependencia funcional real `(id_libro, id_concepto) -> definicion`,
  **no** una dependencia multivaluada. `libro_concepto` no es una tabla puente "de sólo llaves"
  como `libro_autor`/`libro_genero`; es una **entidad asociativa de pleno derecho**, con un
  atributo propio (`definicion`) cuya clave natural es el par completo:

```
LIBRO_CONCEPTO(id_libro FK, id_concepto FK, definicion)   PK (id_libro, id_concepto)
```

Esta relación ya está en BCNF por sí misma (la única FD no trivial es
`(id_libro, id_concepto) -> definicion`, y el determinante es la clave completa), así que no hace
falta ninguna descomposición adicional por 4FN aquí — el "riesgo" de connection trap sólo aplica
cuando dos o más MVDs *independientes* comparten el mismo determinante, y aquí no hay tal MVD,
hay una FD normal sobre una relación N:M con atributo.

## Resultado final (equivalente a `data/library_schema.sql`)

```
USUARIOS(id_usuario PK, nombre_usuario, correo, contrasena_hash, rol, fecha_registro)
FORMATOS(id_formato PK, nombre_formato)
GENEROS(id_genero PK, nombre_genero)
AUTORES(id_autor PK, nombre_autor)
CONCEPTOS(id_concepto PK, nombre_concepto)
LIBROS(id_libro PK, isbn, titulo, anio_publicacion, precio, stock, id_formato FK, fecha_creacion)
LIBRO_AUTOR(id_libro FK, id_autor FK)                         PK compuesta
LIBRO_GENERO(id_libro FK, id_genero FK)                       PK compuesta
LIBRO_CONCEPTO(id_libro FK, id_concepto FK, definicion)       PK compuesta, con atributo propio
IMAGENES_LIBRO(id_imagen PK, id_libro FK, url_imagen, orden, es_portada)
```

Todas las tablas están en 4FN: cada relación tiene, como máximo, una dependencia multivaluada no
trivial (la de su propia clave hacia sus propios atributos, que es trivial), y las cuatro
dependencias multivaluadas independientes originales (autor, género, imagen sobre libro) quedaron
cada una en su propia relación binaria, sin mezclarse entre sí.

## Resumen de anomalías resueltas, por forma normal

| Forma normal alcanzada | Anomalía que ya no ocurre |
|---|---|
| 1FN | Ya no hay listas dentro de una celda; se puede filtrar por autor/género exacto |
| 2FN | El precio/stock/título del libro ya no se repite por cada combinación autor-género |
| 3FN/BCNF | Renombrar un formato, autor, género o concepto es un solo `UPDATE`, no uno por cada libro que lo use |
| 4FN | Agregar un autor nuevo no obliga a duplicar filas por cada género existente (y viceversa); no hay producto cartesiano artificial entre autores, géneros e imágenes |

## Pendiente

- Portar este análisis al formato de plantilla Excel visto en la clase de Bases de Datos
  Avanzadas (`docs/NORMALIZATION_4FN.xlsx`) — se generó una versión inicial en ese archivo con la
  misma información organizada por hojas (UNF, 1FN, 2FN, 3FN/BCNF, 4FN); si el formato exacto de
  la plantilla de clase es distinto, ajustar la estructura de las hojas sin cambiar el contenido.
- Diagrama ER final en `docs/DB_DESIGN_ER_4FN.png` — ver el diagrama Mermaid embebido en
  `html/ejercicio02/index.html` (sección 4) como base; falta exportarlo como imagen estática si se
  requiere el archivo `.png` literal para la entrega.
