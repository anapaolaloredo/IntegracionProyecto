# Electron App — Catálogo de libros (cards) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-11-targeted Electron desktop app in `apps/Electron_app` that shows the book catalog as image cards (image, author(s), ISBN, stock, year, genre, price), with client-side pagination and a configurable, localStorage-persisted microservice URL/endpoint, consuming XML only.

**Architecture:** Same two-process Electron pattern already used by the sibling app `apps/desktop-clasificador-cloud`: the **main process** (plain Node, no CORS) makes the HTTP GET to the cloud microservice and returns the raw XML string over IPC; **preload.js** is the only bridge the renderer gets (`contextIsolation: true`, `nodeIntegration: false`), and it also re-exports two pure, dependency-free helpers — `parsearLibrosXml` (XML string → array of book objects) and `paginar` (array → one page) — from a shared CommonJS module `catalogo.js` that has no DOM/Electron dependency, so it can be unit-tested directly under Node with `node:test` (same test style as `apps/web-monolito01/test`). The **renderer** fetches the full book list once per "Cargar catálogo" click (one HTTP request — this is the "carga por petición" requirement), then paginates entirely client-side: only the cards on the currently visible page are inserted into the DOM, so their `<img>` tags — and therefore their network image downloads — are only requested when that page is shown.

**Tech Stack:** Electron (devDependency only, same version already vendored in the sibling app: `^44.3.0`), plain HTML/CSS/JS, Node's built-in `node:test`/`node:assert` for unit tests. No other npm dependencies — matches the project-wide pattern of the other three apps.

**Spec:** `04_Electron_app.md` (repo root)

## Global Constraints

- Target platform: Windows 11 (per spec point 1 and 3) — README must give Windows-specific run steps; code itself must stay cross-platform (no OS-specific paths), matching how the sibling Electron app is written.
- Directory: the app **must** live at `/apps/Electron_app` exactly (spec point 1).
- Cards must show, per book: image, author(s), ISBN, stock, publication year, genre, price (spec point 1).
- Must implement pagination and load-on-request (spec point 1) — see Architecture above for how "carga por petición" is interpreted, since the real microservice has no server-side page/limit params (verified in `apps/services/soap/app.py:222-233`).
- Must consume **exclusively XML** from the microservice (spec point 2) — `Accept: application/xml`, never parse/accept JSON.
- Base URL and endpoint path must be configurable in the running app and persisted via `localStorage` (spec point 2). The spec names `:5001/books`; the microservice that actually exists exposes `GET /api/libros` on port 5001 (`apps/services/soap/app.py:222`) — `/api/libros` is used as the default endpoint value, and it stays a plain editable text field so it can be pointed at `/books` or anywhere else without touching code.
- Must ship a `README.md` with the steps to run the app on Windows 11 (spec point 3).

---

## File Structure

- `apps/Electron_app/catalogo.js` — pure CommonJS module: XML string → book objects, and pagination slicing. No DOM, no Electron API. This is what gets unit-tested.
- `apps/Electron_app/test/catalogo.test.js` — `node:test` unit tests for the above.
- `apps/Electron_app/main.js` — Electron main process: creates the window, does the HTTP GET to the microservice (avoids CORS, mirrors `apps/desktop-clasificador-cloud/main.js`), exposes it over one `ipcMain.handle`.
- `apps/Electron_app/preload.js` — `contextBridge` bridge: exposes the IPC call plus the two pure helpers from `catalogo.js` to the renderer.
- `apps/Electron_app/index.html` — layout: configuración form (URL base + endpoint + botón "Cargar catálogo"), grid de cards, controles de paginación, caja de error. Styles inlined in a `<style>` block (matches `apps/desktop-clasificador-cloud/index.html` convention).
- `apps/Electron_app/renderer.js` — wiring: reads/persists config in `localStorage`, calls preload APIs, renders the current page of cards, handles Anterior/Siguiente.
- `apps/Electron_app/package.json` — `electron` devDependency, `start` and `test` scripts.
- `apps/Electron_app/README.md` — Windows 11 run steps.

---

### Task 1: `catalogo.js` — XML parsing + pagination (pure, unit-tested)

**Files:**
- Create: `apps/Electron_app/catalogo.js`
- Test: `apps/Electron_app/test/catalogo.test.js`

**Interfaces:**
- Produces: `parsearLibrosXml(xmlTexto: string): Array<{isbn, title, authors: string[], publicationYear, genres: string[], price, currency, stock, format, images: Array<{url, cover: boolean, alt}>}>` — throws `Error(mensaje)` if `xmlTexto` is an `<error><message>...</message></error>` response.
- Produces: `paginar(lista: Array, pagina: number, tamanoPagina: number): {itemsPagina: Array, totalPaginas: number, paginaActual: number}` — clamps `pagina` into `[1, totalPaginas]`.

- [ ] **Step 1: Write the failing tests**

```javascript
// apps/Electron_app/test/catalogo.test.js
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test apps/Electron_app/test/catalogo.test.js`
Expected: FAIL — `Cannot find module '../catalogo.js'`

- [ ] **Step 3: Write the implementation**

```javascript
// apps/Electron_app/catalogo.js
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test apps/Electron_app/test/catalogo.test.js`
Expected: PASS — 6 tests, 0 failures

- [ ] **Step 5: Commit**

```bash
git add apps/Electron_app/catalogo.js apps/Electron_app/test/catalogo.test.js
git commit -m "feat: add pure XML parsing + pagination for the Electron catalog app"
```

---

### Task 2: Electron main process + preload bridge

**Files:**
- Create: `apps/Electron_app/main.js`
- Create: `apps/Electron_app/preload.js`

**Interfaces:**
- Consumes: `require("./catalogo.js")` → `{ parsearLibrosXml, paginar }` (Task 1).
- Produces: `window.catalogApi.obtenerLibrosXml(baseUrl: string, endpoint: string): Promise<string>` (raw XML), `window.catalogApi.parsearLibros(xml: string)`, `window.catalogApi.paginar(lista, pagina, tamanoPagina)` — all consumed by `renderer.js` in Task 4.

There is no automated test for this task: it is Electron-only I/O (window creation, real HTTP) with no test harness in this repo (the sibling app `apps/desktop-clasificador-cloud` has none either for the same reason). Verify manually at the end of Task 5 by actually running the app.

- [ ] **Step 1: Write `main.js`**

```javascript
// apps/Electron_app/main.js
/**
 * Proceso principal de Electron. Igual que en
 * apps/desktop-clasificador-cloud/main.js: el microservicio corre en la
 * nube y esta app corre local, asi que la peticion HTTP se hace aqui
 * (Node puro, sin CORS) y el renderer solo recibe el XML ya descargado.
 */
const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const http = require("http");
const https = require("https");

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile("index.html");
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

/** Descarga XML exigiendo Accept: application/xml (nunca JSON). */
function httpGetXml(urlString) {
  return new Promise((resolve, reject) => {
    let target;
    try {
      target = new URL(urlString);
    } catch {
      reject(new Error(`URL invalida: ${urlString}`));
      return;
    }

    const client = target.protocol === "https:" ? https : http;
    const req = client.get(
      target,
      { headers: { Accept: "application/xml" } },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(body);
          } else {
            reject(
              new Error(`El microservicio respondio con estado ${res.statusCode}: ${body}`)
            );
          }
        });
      }
    );

    req.on("error", (err) => reject(err));
    req.setTimeout(10000, () => {
      req.destroy(new Error("Tiempo de espera agotado al contactar el microservicio"));
    });
  });
}

// baseUrl + endpoint son configurables desde la GUI (ver renderer.js);
// aqui solo se combinan y se descarga el XML.
ipcMain.handle("catalogo:obtener-libros", async (_event, { baseUrl, endpoint }) => {
  const url = new URL(endpoint, baseUrl);
  return httpGetXml(url.toString());
});
```

- [ ] **Step 2: Write `preload.js`**

```javascript
// apps/Electron_app/preload.js
/**
 * Puente seguro entre el renderer (sin acceso a Node/Electron) y el
 * proceso principal, mas los helpers puros de catalogo.js (parseo de XML
 * y paginacion), para que renderer.js no necesite `require`.
 */
const { contextBridge, ipcRenderer } = require("electron");
const { parsearLibrosXml, paginar } = require("./catalogo.js");

contextBridge.exposeInMainWorld("catalogApi", {
  /**
   * @param {string} baseUrl p.ej. http://IP:5001
   * @param {string} endpoint p.ej. /api/libros
   * @returns {Promise<string>} XML crudo
   */
  obtenerLibrosXml: (baseUrl, endpoint) =>
    ipcRenderer.invoke("catalogo:obtener-libros", { baseUrl, endpoint }),
  parsearLibros: (xml) => parsearLibrosXml(xml),
  paginar: (lista, pagina, tamanoPagina) => paginar(lista, pagina, tamanoPagina),
});
```

- [ ] **Step 3: Commit**

```bash
git add apps/Electron_app/main.js apps/Electron_app/preload.js
git commit -m "feat: add Electron main process and preload bridge for the catalog app"
```

---

### Task 3: `index.html` — layout, config form, cards grid, pagination controls

**Files:**
- Create: `apps/Electron_app/index.html`

**Interfaces:**
- Produces: DOM ids consumed by `renderer.js` in Task 4 — `baseUrlInput`, `endpointInput`, `btnCargar`, `errorBox`, `catalogGrid`, `btnAnterior`, `btnSiguiente`, `infoPagina`.

- [ ] **Step 1: Write `index.html`**

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <title>Catalogo de libros</title>
    <style>
      :root {
        --primario: #2563eb;
        --texto: #111827;
        --fondo: #f3f4f6;
      }
      body {
        font-family: -apple-system, "Segoe UI", Arial, sans-serif;
        background: var(--fondo);
        margin: 0;
        padding: 24px;
        color: var(--texto);
      }
      h1 {
        font-size: 1.4rem;
        margin-bottom: 4px;
      }
      .subtitle {
        color: #4b5563;
        margin-top: 0;
        margin-bottom: 20px;
      }
      .panel {
        background: #fff;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      }
      .fila-config {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        align-items: flex-end;
      }
      .campo {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-width: 220px;
      }
      label {
        font-weight: 600;
        margin-bottom: 4px;
        font-size: 0.85rem;
      }
      input {
        padding: 8px 10px;
        border-radius: 6px;
        border: 1px solid #d1d5db;
        font-size: 0.95rem;
      }
      button {
        padding: 9px 16px;
        border: none;
        border-radius: 6px;
        background: var(--primario);
        color: #fff;
        font-weight: 600;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.6;
        cursor: default;
      }
      button.secundario {
        background: #4b5563;
      }
      #errorBox {
        display: none;
        background: #fee2e2;
        color: #991b1b;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 16px;
      }
      #catalogGrid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 16px;
      }
      .card {
        background: #fff;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        display: flex;
        flex-direction: column;
      }
      .card img {
        width: 100%;
        height: 220px;
        object-fit: cover;
        background: #e5e7eb;
      }
      .card .cuerpo {
        padding: 12px 14px;
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .card .titulo {
        font-weight: 700;
        font-size: 1rem;
      }
      .card .dato {
        font-size: 0.85rem;
        color: #374151;
      }
      .card .precio {
        margin-top: auto;
        font-weight: 700;
        color: var(--primario);
      }
      #paginacion {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 16px;
        margin-top: 20px;
      }
    </style>
  </head>
  <body>
    <h1>Catalogo de libros</h1>
    <p class="subtitle">
      Consume, en XML, el microservicio de libros de la nube (configurable
      abajo).
    </p>

    <div class="panel">
      <div class="fila-config">
        <div class="campo">
          <label for="baseUrlInput">URL base del microservicio</label>
          <input id="baseUrlInput" type="text" placeholder="http://IP-DE-LA-NUBE:5001" />
        </div>
        <div class="campo">
          <label for="endpointInput">Endpoint</label>
          <input id="endpointInput" type="text" placeholder="/api/libros" />
        </div>
        <button id="btnCargar">Cargar catalogo</button>
      </div>
    </div>

    <div id="errorBox"></div>

    <div id="catalogGrid"></div>

    <div id="paginacion">
      <button id="btnAnterior" class="secundario">Anterior</button>
      <span id="infoPagina">Sin datos</span>
      <button id="btnSiguiente" class="secundario">Siguiente</button>
    </div>

    <script src="renderer.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add apps/Electron_app/index.html
git commit -m "feat: add catalog app layout (config form, card grid, pagination controls)"
```

---

### Task 4: `renderer.js` — wiring, config persistence, pagination

**Files:**
- Create: `apps/Electron_app/renderer.js`

**Interfaces:**
- Consumes: `window.catalogApi.obtenerLibrosXml`, `window.catalogApi.parsearLibros`, `window.catalogApi.paginar` (Task 2); DOM ids from Task 3.

- [ ] **Step 1: Write `renderer.js`**

```javascript
// apps/Electron_app/renderer.js
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
const ENDPOINT_POR_DEFECTO = "/api/libros";

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
    <div class="dato">Genero: ${libro.genres.join(", ") || "-"}</div>
    <div class="dato">Stock: ${libro.stock}</div>
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
```

- [ ] **Step 2: Commit**

```bash
git add apps/Electron_app/renderer.js
git commit -m "feat: wire catalog app renderer (config, fetch, client-side pagination)"
```

---

### Task 5: `package.json`, `README.md`, and manual end-to-end verification

**Files:**
- Create: `apps/Electron_app/package.json`
- Create: `apps/Electron_app/README.md`

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "electron-app-catalogo",
  "version": "1.0.0",
  "description": "App de escritorio (Electron, Windows 11) que muestra el catalogo de libros en tarjetas, consumiendo XML de un microservicio con URL/endpoint configurables",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "test": "node --test test/"
  },
  "devDependencies": {
    "electron": "^44.3.0"
  }
}
```

- [ ] **Step 2: Write `README.md`**

```markdown
# Electron App — Catalogo de libros

App de escritorio (Electron) que muestra el catalogo de libros de la
biblioteca en tarjetas (imagen, autor(es), ISBN, stock, anio, genero y
precio), con paginacion, consumiendo unicamente XML de un microservicio
en la nube cuya URL y endpoint son configurables desde la propia app.

## Requisitos (Windows 11)

- Node.js LTS (18 o superior) instalado — https://nodejs.org
- El microservicio de libros (`apps/services/soap`) accesible por red desde
  esta maquina (por defecto expone `GET /api/libros` en el puerto 5001).

## Instalacion

Desde una terminal (PowerShell o CMD) dentro de la carpeta del proyecto:

```powershell
cd apps\Electron_app
npm install
```

## Ejecucion

```powershell
npm start
```

Al abrir la app:

1. En "URL base del microservicio" escribe la URL del servidor en la nube,
   por ejemplo `http://34.10.20.30:5001`.
2. En "Endpoint" deja `/api/libros` (valor por defecto) o cambialo si el
   microservicio expone otra ruta.
3. Pulsa "Cargar catalogo". La URL y el endpoint quedan guardados
   (localStorage) para la siguiente vez que abras la app.
4. Usa "Anterior" / "Siguiente" para paginar el catalogo ya descargado.

## Pruebas unitarias

El parseo de XML y la paginacion (`catalogo.js`) no dependen de Electron ni
del DOM, asi que se prueban con el runner de pruebas incluido en Node:

```powershell
npm test
```
```

- [ ] **Step 3: Install dependencies and run the unit test suite**

Run: `cd apps/Electron_app && npm install && npm test`
Expected: `npm install` completes (fetches Electron), `npm test` reports the 6 tests from Task 1 passing.

- [ ] **Step 4: Manual end-to-end verification**

Run: `cd apps/Electron_app && npm start`
Expected:
- A window opens showing the config form, an empty grid, and "Sin datos" pagination text.
- With a reachable `apps/services/soap` instance running locally (`cd apps/services/soap && python app.py`, default `http://localhost:5001`), type `http://localhost:5001` as the base URL, keep `/api/libros`, click "Cargar catalogo": cards appear with cover image, authors, ISBN, year, genre, stock and price.
- "Siguiente"/"Anterior" move between pages without any extra network request (check via the OS network monitor or by stopping the Flask server after the first load — pagination must keep working).
- Quitting and reopening the app pre-fills the URL/endpoint fields and auto-loads the catalog (localStorage persistence).
- An invalid base URL shows the red error box with a readable message instead of crashing.

- [ ] **Step 5: Commit**

```bash
git add apps/Electron_app/package.json apps/Electron_app/README.md
git commit -m "docs: add Windows 11 run steps and package scripts for the catalog app"
```

---

## Self-Review

**Spec coverage:**
- Spec point 1 (Electron app, Windows 11 target, cards with image/authors/ISBN/stock/year/genre/price, pagination, load-on-request, directory `/apps/Electron_app`) → Tasks 1, 3, 4, 5.
- Spec point 2 (exclusively XML, configurable URL/endpoint, persisted in localStorage) → Tasks 1 (parsing), 2 (`Accept: application/xml`, no JSON anywhere), 4 (config form + localStorage).
- Spec point 3 (README with Windows 11 run steps) → Task 5.

**Placeholder scan:** none — every step has runnable code or a concrete manual-verification checklist.

**Type consistency:** `catalogo.js` exports `parsearLibrosXml`/`paginar` (Task 1) and both are required verbatim in `preload.js` (Task 2) and called through `window.catalogApi.parsearLibros`/`window.catalogApi.paginar` in `renderer.js` (Task 4) — names match end to end. The book object shape (`isbn, title, authors, publicationYear, genres, price, currency, stock, format, images`) is produced once in Task 1 and consumed with the same field names in Task 4's `crearCard`/`urlImagenPrincipal`.
