/**
 * Logica de la interfaz. Sin acceso a Node ni red directa: todo pasa por
 * window.catalogApi (expuesto en preload.js). Un solo GET por click en
 * "Cargar catalogo" (esa es la peticion); la paginacion despues solo
 * recorta el arreglo ya descargado, asi que las imagenes de una pagina
 * solo se piden a la red cuando esa pagina se muestra.
 */

const TAMANO_PAGINA = 8;
const CLAVE_BASE_URL = "catalogo.baseUrl";
const CLAVE_ENDPOINT = "catalogo.endpoint";
const ENDPOINT_POR_DEFECTO = "/api/libros/catalogo";

let libros = [];
let paginaActual = 1;

function mostrarError(mensaje) {
  const box = document.getElementById("errorBox");
  box.textContent = mensaje;
  box.style.display = mensaje ? "block" : "none";
}

function urlImagenPrincipal(libro) {
  const portada = libro.images.find((img) => img.cover) || libro.images[0];
  return portada ? portada.url : "";
}

function crearCard(libro) {
  const card = document.createElement("div");
  card.className = "card";

  const img = document.createElement("img");
  const urlImagen = urlImagenPrincipal(libro);
  img.src = urlImagen || "";
  img.alt = libro.title;
  if (!urlImagen) img.style.display = "none";
  card.appendChild(img);

  const cuerpo = document.createElement("div");
  cuerpo.className = "cuerpo";
  cuerpo.innerHTML = `
    <div class="titulo">${libro.title}</div>
    <div class="dato">${libro.authors.join(", ") || "Autor desconocido"}</div>
    <div class="dato">ISBN: ${libro.isbn}</div>
    <div class="dato">Anio: ${libro.publicationYear || "-"}</div>
    <div class="precio">${libro.price} ${libro.currency}</div>
  `;
  card.appendChild(cuerpo);

  return card;
}

function renderPagina() {
  const grid = document.getElementById("catalogGrid");
  grid.innerHTML = "";

  if (libros.length === 0) {
    document.getElementById("infoPagina").textContent = "Sin datos";
    document.getElementById("btnAnterior").disabled = true;
    document.getElementById("btnSiguiente").disabled = true;
    return;
  }

  const { itemsPagina, totalPaginas, paginaActual: paginaCorregida } =
    window.catalogApi.paginar(libros, paginaActual, TAMANO_PAGINA);
  paginaActual = paginaCorregida;

  for (const libro of itemsPagina) {
    grid.appendChild(crearCard(libro));
  }

  document.getElementById("infoPagina").textContent =
    `Pagina ${paginaActual} de ${totalPaginas}`;
  document.getElementById("btnAnterior").disabled = paginaActual <= 1;
  document.getElementById("btnSiguiente").disabled = paginaActual >= totalPaginas;
}

async function cargarCatalogo() {
  mostrarError("");
  const baseUrl = document.getElementById("baseUrlInput").value.trim();
  const endpoint = document.getElementById("endpointInput").value.trim() || ENDPOINT_POR_DEFECTO;

  if (!baseUrl) {
    mostrarError("Indica la URL base del microservicio.");
    return;
  }

  localStorage.setItem(CLAVE_BASE_URL, baseUrl);
  localStorage.setItem(CLAVE_ENDPOINT, endpoint);

  const boton = document.getElementById("btnCargar");
  boton.disabled = true;
  boton.textContent = "Cargando...";

  try {
    const xml = await window.catalogApi.obtenerLibrosXml(baseUrl, endpoint);
    libros = window.catalogApi.parsearLibros(xml);
    paginaActual = 1;
    renderPagina();
  } catch (err) {
    libros = [];
    renderPagina();
    mostrarError(`No se pudo cargar el catalogo: ${err.message}`);
  } finally {
    boton.disabled = false;
    boton.textContent = "Cargar catalogo";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const baseGuardada = localStorage.getItem(CLAVE_BASE_URL);
  const endpointGuardado = localStorage.getItem(CLAVE_ENDPOINT);
  if (baseGuardada) document.getElementById("baseUrlInput").value = baseGuardada;
  document.getElementById("endpointInput").value = endpointGuardado || ENDPOINT_POR_DEFECTO;

  document.getElementById("btnCargar").addEventListener("click", cargarCatalogo);
  document.getElementById("btnAnterior").addEventListener("click", () => {
    paginaActual -= 1;
    renderPagina();
  });
  document.getElementById("btnSiguiente").addEventListener("click", () => {
    paginaActual += 1;
    renderPagina();
  });

  renderPagina();
  if (baseGuardada) cargarCatalogo();
});
