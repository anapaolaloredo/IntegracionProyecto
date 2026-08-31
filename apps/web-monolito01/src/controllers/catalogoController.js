// Fabrica de controladores CRUD para los catalogos simples (id, nombre).
// vista: carpeta de vistas en src/views/<vista>/
// campoNombre: nombre del campo de formulario (p.ej. "nombre_formato")
// idCampo: nombre de la columna id (p.ej. "id_formato")
function crearCatalogoController(modelo, vista, campoNombre, etiqueta, idCampo) {
  const idCampoReal = idCampo || `id_${vista.slice(0, -1)}`; // p.ej. "formatos" -> "id_formato"

  return {
    async listar(req, res) {
      const items = await modelo.listar();
      res.render(`${vista}/listar`, { items, etiqueta, vista, idCampo: idCampoReal, campoNombre });
    },

    mostrarCrear(req, res) {
      res.render(`${vista}/crear`, { error: null, etiqueta, vista, campoNombre, valores: {} });
    },

    async crear(req, res) {
      const nombre = req.body[campoNombre];
      try {
        if (!nombre || !nombre.trim()) throw new Error(`El nombre de ${etiqueta} es obligatorio.`);
        await modelo.crear(nombre.trim());
        res.redirect(`${res.locals.basePath}/${vista}`);
      } catch (err) {
        res.status(400).render(`${vista}/crear`, { error: err.message, etiqueta, vista, campoNombre, valores: req.body });
      }
    },

    async mostrarEditar(req, res) {
      const items = await modelo.listar();
      const item = items.find((i) => String(i[idCampoReal]) === req.params.id);
      if (!item) return res.status(404).render('error', { titulo: 'No encontrado', mensaje: `${etiqueta} no encontrado.` });
      res.render(`${vista}/editar`, { item, error: null, etiqueta, vista, campoNombre, idCampo: idCampoReal });
    },

    async actualizar(req, res) {
      const { id } = req.params;
      const nombre = req.body[campoNombre];
      try {
        if (!nombre || !nombre.trim()) throw new Error(`El nombre de ${etiqueta} es obligatorio.`);
        await modelo.actualizar(id, nombre.trim());
        res.redirect(`${res.locals.basePath}/${vista}`);
      } catch (err) {
        const item = { [idCampoReal]: id, [campoNombre]: nombre };
        res.status(400).render(`${vista}/editar`, { item, error: err.message, etiqueta, vista, campoNombre, idCampo: idCampoReal });
      }
    },

    async eliminar(req, res) {
      try {
        await modelo.eliminar(req.params.id);
      } catch (err) {
        req.session.mensajeError = 'No se pudo eliminar: probablemente esta en uso por uno o mas libros.';
      }
      res.redirect(`${res.locals.basePath}/${vista}`);
    }
  };
}

module.exports = crearCatalogoController;
