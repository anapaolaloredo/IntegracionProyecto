const test = require("node:test");
const assert = require("node:assert");
const { parsearLibrosXml, paginar } = require("../catalogo.js");

const XML_UN_LIBRO = `<?xml version='1.0' encoding='utf-8'?>
<library>
  <book isbn="9780307474728">
    <title>El Se&amp;ntildeor de los Anillos</title>
    <authors><author>J.R.R. Tolkien</author></authors>
    <publicationYear>1954</publicationYear>
    <genres><genre>Fantasia</genre></genres>
    <price currency="MXN">450.00</price>
    <stock>12</stock>
    <format>Tapa dura</format>
    <images><image cover="true" alt="Portada">https://covers.openlibrary.org/b/isbn/9780307474728-L.jpg</image></images>
    <concepts></concepts>
  </book>
</library>`;

const XML_DOS_AUTORES_DOS_GENEROS = `<?xml version='1.0' encoding='utf-8'?>
<library>
  <book isbn="1111111111">
    <title>Libro Colaborativo</title>
    <authors><author>Autor Uno</author><author>Autor Dos</author></authors>
    <publicationYear>2020</publicationYear>
    <genres><genre>Drama</genre><genre>Historia</genre></genres>
    <price currency="MXN">200.00</price>
    <stock>3</stock>
    <format>Digital</format>
    <images></images>
    <concepts></concepts>
  </book>
</library>`;

const XML_VACIO = `<?xml version='1.0' encoding='utf-8'?><library></library>`;

// Forma real de GET /api/libros/catalogo (apps/services/soap/app.py):
// solo isbn, title, authors, publicationYear, price e images -- sin
// genres/stock/format/concepts.
const XML_CATALOGO_MINIMO = `<?xml version='1.0' encoding='utf-8'?>
<library>
  <book isbn="9780451524935">
    <title>1984</title>
    <authors><author>George Orwell</author></authors>
    <publicationYear>1949</publicationYear>
    <price currency="MXN">300.00</price>
    <images><image cover="true" alt="Portada">https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg</image></images>
  </book>
</library>`;

const XML_ERROR = `<?xml version='1.0' encoding='utf-8'?><error><message>ISBN no encontrado</message></error>`;

test("parsearLibrosXml extrae todos los campos de un libro", () => {
  const libros = parsearLibrosXml(XML_UN_LIBRO);
  assert.strictEqual(libros.length, 1);
  const libro = libros[0];
  assert.strictEqual(libro.isbn, "9780307474728");
  assert.strictEqual(libro.title, "El Se&ntildeor de los Anillos");
  assert.deepStrictEqual(libro.authors, ["J.R.R. Tolkien"]);
  assert.strictEqual(libro.publicationYear, "1954");
  assert.deepStrictEqual(libro.genres, ["Fantasia"]);
  assert.strictEqual(libro.price, "450.00");
  assert.strictEqual(libro.currency, "MXN");
  assert.strictEqual(libro.stock, "12");
  assert.strictEqual(libro.format, "Tapa dura");
  assert.deepStrictEqual(libro.images, [
    { url: "https://covers.openlibrary.org/b/isbn/9780307474728-L.jpg", cover: true, alt: "Portada" },
  ]);
});

test("parsearLibrosXml soporta varios autores y varios generos", () => {
  const libros = parsearLibrosXml(XML_DOS_AUTORES_DOS_GENEROS);
  assert.deepStrictEqual(libros[0].authors, ["Autor Uno", "Autor Dos"]);
  assert.deepStrictEqual(libros[0].genres, ["Drama", "Historia"]);
  assert.deepStrictEqual(libros[0].images, []);
});

test("parsearLibrosXml soporta el XML minimo de /api/libros/catalogo (sin genero/stock/formato)", () => {
  const libros = parsearLibrosXml(XML_CATALOGO_MINIMO);
  assert.strictEqual(libros.length, 1);
  const libro = libros[0];
  assert.strictEqual(libro.isbn, "9780451524935");
  assert.strictEqual(libro.title, "1984");
  assert.deepStrictEqual(libro.authors, ["George Orwell"]);
  assert.strictEqual(libro.publicationYear, "1949");
  assert.strictEqual(libro.price, "300.00");
  assert.strictEqual(libro.currency, "MXN");
  assert.deepStrictEqual(libro.genres, []);
  assert.strictEqual(libro.stock, "");
  assert.strictEqual(libro.format, "");
  assert.deepStrictEqual(libro.images, [
    { url: "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg", cover: true, alt: "Portada" },
  ]);
});

test("parsearLibrosXml devuelve arreglo vacio para <library></library>", () => {
  assert.deepStrictEqual(parsearLibrosXml(XML_VACIO), []);
});

test("parsearLibrosXml lanza con el mensaje del <error> del microservicio", () => {
  assert.throws(() => parsearLibrosXml(XML_ERROR), /ISBN no encontrado/);
});

test("paginar corta la lista y calcula el total de paginas", () => {
  const lista = Array.from({ length: 10 }, (_, i) => i + 1);
  const { itemsPagina, totalPaginas, paginaActual } = paginar(lista, 2, 4);
  assert.deepStrictEqual(itemsPagina, [5, 6, 7, 8]);
  assert.strictEqual(totalPaginas, 3);
  assert.strictEqual(paginaActual, 2);
});

test("paginar limita la pagina solicitada al rango valido", () => {
  const lista = [1, 2, 3];
  assert.strictEqual(paginar(lista, 0, 2).paginaActual, 1);
  assert.strictEqual(paginar(lista, 99, 2).paginaActual, 2);
});
