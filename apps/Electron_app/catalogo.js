/**
 * Parseo del XML del microservicio de libros y paginacion, sin DOM ni
 * dependencias externas, para poder probarse con node:test tal cual
 * (se reusa desde preload.js dentro de Electron).
 */

function desescaparXml(texto) {
  return texto
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

function extraerBloque(bloque, tag) {
  const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`);
  const match = bloque.match(regex);
  return match ? match[1] : "";
}

function extraerTexto(bloque, tag) {
  const contenido = extraerBloque(bloque, tag);
  return contenido ? desescaparXml(contenido) : "";
}

function extraerAtributo(etiquetaAbierta, nombreAtributo) {
  const regex = new RegExp(`${nombreAtributo}="([^"]*)"`);
  const match = etiquetaAbierta.match(regex);
  return match ? desescaparXml(match[1]) : "";
}

function extraerListaTexto(bloque, tagContenedor, tagItem) {
  const contenedor = extraerBloque(bloque, tagContenedor);
  const regex = new RegExp(`<${tagItem}>([\\s\\S]*?)</${tagItem}>`, "g");
  const resultado = [];
  let match;
  while ((match = regex.exec(contenedor)) !== null) {
    resultado.push(desescaparXml(match[1]));
  }
  return resultado;
}

function extraerImagenes(bloque) {
  const contenedor = extraerBloque(bloque, "images");
  const regex = /<image([^>]*)>([\s\S]*?)<\/image>/g;
  const resultado = [];
  let match;
  while ((match = regex.exec(contenedor)) !== null) {
    resultado.push({
      url: desescaparXml(match[2]),
      cover: extraerAtributo(match[1], "cover") === "true",
      alt: extraerAtributo(match[1], "alt"),
    });
  }
  return resultado;
}

/**
 * Convierte el XML de GET <endpoint configurado> (misma forma que
 * apps/services/soap/app.py:149 books_xml_response) en objetos JS.
 * Lanza Error(mensaje) si el microservicio respondio un <error>.
 */
function parsearLibrosXml(xmlTexto) {
  const errorMatch = xmlTexto.match(
    /<error>[\s\S]*?<message>([\s\S]*?)<\/message>[\s\S]*?<\/error>/
  );
  if (errorMatch) {
    throw new Error(desescaparXml(errorMatch[1]));
  }

  const resultado = [];
  const regexLibro = /<book\s+([^>]*)>([\s\S]*?)<\/book>/g;
  let match;
  while ((match = regexLibro.exec(xmlTexto)) !== null) {
    const atributosLibro = match[1];
    const cuerpo = match[2];
    const precioMatch = cuerpo.match(/<price([^>]*)>([\s\S]*?)<\/price>/);

    resultado.push({
      isbn: extraerAtributo(atributosLibro, "isbn"),
      title: extraerTexto(cuerpo, "title"),
      authors: extraerListaTexto(cuerpo, "authors", "author"),
      publicationYear: extraerTexto(cuerpo, "publicationYear"),
      genres: extraerListaTexto(cuerpo, "genres", "genre"),
      price: precioMatch ? desescaparXml(precioMatch[2]) : "",
      currency: precioMatch ? extraerAtributo(precioMatch[1], "currency") : "",
      stock: extraerTexto(cuerpo, "stock"),
      format: extraerTexto(cuerpo, "format"),
      images: extraerImagenes(cuerpo),
    });
  }
  return resultado;
}

/** Pagina en memoria; no vuelve a pedir datos al microservicio. */
function paginar(lista, pagina, tamanoPagina) {
  const totalPaginas = Math.max(1, Math.ceil(lista.length / tamanoPagina));
  const paginaActual = Math.min(Math.max(1, pagina), totalPaginas);
  const inicio = (paginaActual - 1) * tamanoPagina;
  return {
    itemsPagina: lista.slice(inicio, inicio + tamanoPagina),
    totalPaginas,
    paginaActual,
  };
}

module.exports = { parsearLibrosXml, paginar };
