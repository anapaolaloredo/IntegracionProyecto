/**
 * Pestana "Asistente": un chat sencillo que responde solo con el catalogo de
 * libros. Sin acceso a Node ni a la red: todo pasa por window.catalogApi y
 * window.ollamaApi (preload.js). El catalogo completo (/api/libros) se manda
 * como contexto en cada pregunta; si tiene mas de 30 s se vuelve a pedir, asi
 * que el stock y los precios que ve el modelo siempre estan al dia.
 */
(() => {
  const CLAVE_URL = "ollama.url";
  const CLAVE_MODELO = "ollama.modelo";
  const CLAVE_FILTRO = "ollama.filtro";
  const URL_POR_DEFECTO = "http://localhost:11434";
  const MODELO_POR_DEFECTO = "qwen2.5:3b";
  const ENDPOINT_CONTEXTO = "/api/libros"; // el completo: precio, existencias, generos y conceptos
  const EDAD_MAX_CONTEXTO_MS = 30000;
  const MAX_HISTORIAL = 20;
  const SUGERENCIAS = [
    "¿Qué libros hay en el catálogo?",
    "¿Cuál es el libro más barato?",
    "¿Qué libros tienen pocas existencias?",
    "Recomiéndame algo de ciencia ficción",
  ];

  const $ = (id) => document.getElementById(id);
  let libros = [];
  let cargadoEn = 0;
  let historial = [];
  let enCurso = null; // id de la pregunta en proceso
  let contador = 0;

  function estado(texto, error = false) {
    const caja = $("estadoChat");
    caja.textContent = texto;
    caja.classList.toggle("error", error);
  }

  function burbuja(rol, texto, extra = "") {
    const b = document.createElement("div");
    b.className = `burbuja ${rol} ${extra}`.trim();
    b.textContent = texto; // textContent: nunca se interpreta HTML de la respuesta del modelo
    $("mensajes").appendChild(b);
    $("mensajes").scrollTop = $("mensajes").scrollHeight;
    return b;
  }

  function leerConfig() {
    return {
      baseUrl: $("ollamaUrlInput").value.trim() || URL_POR_DEFECTO,
      model: $("ollamaModeloInput").value.trim() || MODELO_POR_DEFECTO,
      filtro: $("filtroEstricto").checked,
    };
  }

  function guardarConfig() {
    const c = leerConfig();
    localStorage.setItem(CLAVE_URL, c.baseUrl);
    localStorage.setItem(CLAVE_MODELO, c.model);
    localStorage.setItem(CLAVE_FILTRO, c.filtro ? "1" : "0");
  }

  function ocupado(si) {
    $("btnEnviar").hidden = si;
    $("btnDetener").hidden = !si;
    $("preguntaInput").disabled = si;
    if (!si) $("preguntaInput").focus();
  }

  /** Pide el catalogo completo al microservicio de libros (misma URL base de la pestaña Catálogo). */
  async function cargarContexto() {
    const baseUrl = $("baseUrlInput").value.trim();
    if (!baseUrl) throw new Error("Indica primero la URL del microservicio de libros en la pestaña Catálogo.");
    let xml;
    try {
      xml = await window.catalogApi.obtenerLibrosXml(baseUrl, ENDPOINT_CONTEXTO);
    } catch (e) {
      // un tropiezo momentáneo de red hacia la nube no debería costar la pregunta: un reintento
      xml = await window.catalogApi.obtenerLibrosXml(baseUrl, ENDPOINT_CONTEXTO);
    }
    libros = window.catalogApi.parsearLibros(xml);
    cargadoEn = Date.now();
    const hora = new Date().toLocaleTimeString();
    estado(libros.length
      ? `Catálogo cargado: ${libros.length} libros · ${hora}`
      : "El catálogo está vacío: el asistente no tendrá nada que responder.", libros.length === 0);
  }

  async function asegurarContexto() {
    if (libros.length && Date.now() - cargadoEn < EDAD_MAX_CONTEXTO_MS) return;
    try {
      await cargarContexto();
    } catch (e) {
      if (!libros.length) throw e;
      estado(`No se pudo actualizar el catálogo (${e.message}); se usa la última copia.`, true);
    }
  }

  async function enviar(evento) {
    evento.preventDefault();
    const pregunta = $("preguntaInput").value.trim();
    if (!pregunta || enCurso) return;
    guardarConfig();
    const { baseUrl, model, filtro } = leerConfig();

    burbuja("usuario", pregunta);
    $("preguntaInput").value = "";
    ocupado(true);
    const id = `q${++contador}`;
    enCurso = id;
    let pendiente = null;
    try {
      try {
        await asegurarContexto();
      } catch (e) {
        burbuja("asistente", `No se pudo cargar el catálogo: ${e.message}`, "error");
        return;
      }

      if (filtro) {
        pendiente = burbuja("asistente", "Verificando que la pregunta sea del catálogo…", "pensando");
        const f = await window.ollamaApi.filtro({ id, baseUrl, model, libros, historial, pregunta });
        pendiente.remove();
        pendiente = null;
        if (!f.ok) {
          if (!f.abortado) burbuja("asistente", f.error, "error");
          return;
        }
        if (!f.delCatalogo) {
          burbuja("asistente", window.ollamaApi.FRASE_RECHAZO, "rechazo");
          estado("El filtro estricto marcó la última pregunta como ajena al catálogo. Si sí lo era, reformúlala " +
            "mencionando el libro o el autor, o desactiva el filtro.");
          return;
        }
      }

      pendiente = burbuja("asistente", "Pensando…", "pensando");
      let recibido = "";
      const r = await window.ollamaApi.chat(
        { id, baseUrl, model, mensajes: window.ollamaApi.construirMensajes(libros, historial, pregunta) },
        (token) => {
          recibido += token;
          pendiente.classList.remove("pensando");
          pendiente.textContent = recibido;
          $("mensajes").scrollTop = $("mensajes").scrollHeight;
        });
      if (r.ok) {
        historial.push({ role: "user", content: pregunta }, { role: "assistant", content: r.texto });
        historial = historial.slice(-MAX_HISTORIAL);
        if (!r.texto.trim()) pendiente.textContent = "(el modelo no devolvió texto)";
      } else if (r.abortado) {
        pendiente.classList.remove("pensando");
        pendiente.textContent = (recibido ? recibido + " " : "") + "(respuesta detenida)";
      } else {
        pendiente.remove();
        burbuja("asistente", r.error, "error");
      }
      pendiente = null;
    } catch (e) {
      if (pendiente) pendiente.remove();
      burbuja("asistente", `Error inesperado: ${e.message}`, "error");
    } finally {
      enCurso = null;
      ocupado(false);
    }
  }

  async function probarConexion() {
    guardarConfig();
    const { baseUrl, model } = leerConfig();
    $("btnProbarOllama").disabled = true;
    estado("Probando conexión con Ollama…");
    const r = await window.ollamaApi.modelos(baseUrl);
    $("btnProbarOllama").disabled = false;
    if (!r.ok) {
      estado(r.error, true);
      return;
    }
    const lista = $("ollamaModelos");
    lista.innerHTML = "";
    for (const nombre of r.modelos) {
      const o = document.createElement("option");
      o.value = nombre;
      lista.appendChild(o);
    }
    if (!r.modelos.includes(model)) {
      estado(`Conectado, pero el modelo «${model}» no está descargado. Modelos disponibles: ${r.modelos.join(", ") || "ninguno"}. ` +
        `Descárgalo con: docker exec <contenedor> ollama pull ${model}`, true);
    } else {
      estado(`Conectado a Ollama. Modelo «${model}» disponible (${r.modelos.length} modelo(s) instalados).`);
    }
  }

  function mostrarVista(nombre) {
    const asistente = nombre === "asistente";
    $("vistaCatalogo").hidden = asistente;
    $("vistaAsistente").hidden = !asistente;
    $("tabCatalogo").classList.toggle("activa", !asistente);
    $("tabAsistente").classList.toggle("activa", asistente);
    if (asistente) {
      $("preguntaInput").focus();
      if (!libros.length) {
        cargarContexto().catch((e) => estado(e.message, true));
      }
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    $("ollamaUrlInput").value = localStorage.getItem(CLAVE_URL) || URL_POR_DEFECTO;
    $("ollamaModeloInput").value = localStorage.getItem(CLAVE_MODELO) || MODELO_POR_DEFECTO;
    $("filtroEstricto").checked = localStorage.getItem(CLAVE_FILTRO) !== "0";

    $("tabCatalogo").addEventListener("click", () => mostrarVista("catalogo"));
    $("tabAsistente").addEventListener("click", () => mostrarVista("asistente"));
    $("formChat").addEventListener("submit", enviar);
    $("btnDetener").addEventListener("click", () => {
      if (enCurso) window.ollamaApi.cancelar(enCurso);
    });
    $("btnProbarOllama").addEventListener("click", probarConexion);
    $("btnActualizarContexto").addEventListener("click", () => {
      cargarContexto().catch((e) => estado(e.message, true));
    });
    for (const texto of SUGERENCIAS) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = texto;
      b.addEventListener("click", () => {
        if (enCurso) return;
        $("preguntaInput").value = texto;
        $("formChat").requestSubmit();
      });
      $("sugerencias").appendChild(b);
    }
    burbuja("asistente", "Hola, soy el asistente de la librería. Pregúntame por precios, existencias, autores o géneros del catálogo.");
  });
})();
