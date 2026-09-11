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
