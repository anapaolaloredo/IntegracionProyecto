/**
 * Puente seguro entre el renderer (sin acceso a Node/Electron) y el
 * proceso principal, mas los helpers puros de catalogo.js (parseo de XML
 * y paginacion), para que renderer.js no necesite `require`.
 */
const { contextBridge, ipcRenderer } = require("electron");
const { parsearLibrosXml, paginar } = require("./catalogo.js");
const { FRASE_RECHAZO, construirMensajes } = require("./ollama.js");

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

contextBridge.exposeInMainWorld("ollamaApi", {
  FRASE_RECHAZO,
  /** Arma los mensajes (sistema con el catalogo + historial + pregunta). */
  construirMensajes: (libros, historial, pregunta) => construirMensajes(libros, historial, pregunta),
  /** Respuesta en streaming: onToken(texto) por fragmento; resuelve { ok, texto | error }. */
  chat: ({ id, baseUrl, model, mensajes }, onToken) => {
    const escuchar = (_event, msg) => {
      if (msg.id === id) onToken(msg.token);
    };
    ipcRenderer.on("ollama:token", escuchar);
    return ipcRenderer
      .invoke("ollama:chat", { id, baseUrl, model, mensajes })
      .finally(() => ipcRenderer.removeListener("ollama:token", escuchar));
  },
  /** Filtro previo: resuelve { ok, delCatalogo | error }. */
  filtro: (args) => ipcRenderer.invoke("ollama:filtro", args),
  cancelar: (id) => ipcRenderer.invoke("ollama:cancelar", id),
  modelos: (baseUrl) => ipcRenderer.invoke("ollama:modelos", baseUrl),
});
