const fs = require('fs');
const path = require('path');
const LibroModel = require('../models/libroModel');
const { FormatoModel, GeneroModel, AutorModel, ConceptoModel } = require('../models/catalogoModel');

const LibroController = {
  async catalogo(req, res) {
    const libros = await LibroModel.listarConDetalle();
    res.render('libros/catalogo', { libros });
  },

  async detalle(req, res) {
    const libro = await LibroModel.obtenerPorId(req.params.id);
    if (!libro) return res.status(404).render('error', { titulo: 'No encontrado', mensaje: 'Libro no encontrado.' });

    const [autores, generos, conceptos, imagenes, formatos, catalogoConceptos] = await Promise.all([
      LibroModel.listarAutoresPorLibro(libro.id_libro),
      LibroModel.listarGenerosPorLibro(libro.id_libro),
      LibroModel.listarConceptosPorLibro(libro.id_libro),
      LibroModel.listarImagenesPorLibro(libro.id_libro),
      FormatoModel.listar(),
      ConceptoModel.listar()
    ]);
    const formato = formatos.find((f) => f.id_formato === libro.id_formato);

    res.render('libros/detalle', { libro, autores, generos, conceptos, imagenes, formato, catalogoConceptos });
  },

  async mostrarCrear(req, res) {
    const [formatos, generos, autores, conceptos] = await Promise.all([
      FormatoModel.listar(), GeneroModel.listar(), AutorModel.listar(), ConceptoModel.listar()
    ]);
    res.render('libros/crear', { formatos, generos, autores, conceptos, error: null, valores: {} });
  },

  async crear(req, res) {
    const { isbn, titulo, anio_publicacion, precio, stock, id_formato } = req.body;
    const idsAutores = [].concat(req.body.autores || []);
    const idsGeneros = [].concat(req.body.generos || []);

    try {
      if (!isbn || !titulo || !id_formato) throw new Error('ISBN, titulo y formato son obligatorios.');
      if (idsAutores.length === 0) throw new Error('Debes asociar al menos un autor.');
      if (idsGeneros.length === 0) throw new Error('Debes asociar al menos un genero.');

      const idLibro = await LibroModel.crear({
        isbn, titulo,
        anio: anio_publicacion || null,
        precio, stock: stock || 0,
        idFormato: id_formato
      });

      for (const idAutor of idsAutores) await LibroModel.asociarAutor(idLibro, idAutor);
      for (const idGenero of idsGeneros) await LibroModel.asociarGenero(idLibro, idGenero);

      res.redirect(`/libros/${idLibro}`);
    } catch (err) {
      const [formatos, generos, autores, conceptos] = await Promise.all([
        FormatoModel.listar(), GeneroModel.listar(), AutorModel.listar(), ConceptoModel.listar()
      ]);
      res.status(400).render('libros/crear', {
        formatos, generos, autores, conceptos,
        error: err.message,
        valores: req.body
      });
    }
  },

  async mostrarEditar(req, res) {
    const libro = await LibroModel.obtenerPorId(req.params.id);
    if (!libro) return res.status(404).render('error', { titulo: 'No encontrado', mensaje: 'Libro no encontrado.' });
    const [formatos, generos, autores, conceptos, generosLibro, autoresLibro] = await Promise.all([
      FormatoModel.listar(), GeneroModel.listar(), AutorModel.listar(), ConceptoModel.listar(),
      LibroModel.listarGenerosPorLibro(libro.id_libro),
      LibroModel.listarAutoresPorLibro(libro.id_libro)
    ]);
    res.render('libros/editar', {
      libro, formatos, generos, autores, conceptos,
      idsGenerosLibro: generosLibro.map((g) => g.id_genero),
      idsAutoresLibro: autoresLibro.map((a) => a.id_autor),
      error: null
    });
  },

  async actualizar(req, res) {
    const { id } = req.params;
    const { titulo, anio_publicacion, precio, stock, id_formato } = req.body;
    const idsAutores = [].concat(req.body.autores || []);
    const idsGeneros = [].concat(req.body.generos || []);
    try {
      await LibroModel.actualizar(id, {
        titulo, anio: anio_publicacion || null, precio, stock: stock || 0, idFormato: id_formato
      });

      // Resincroniza autores del libro
      const autoresActuales = (await LibroModel.listarAutoresPorLibro(id)).map((a) => String(a.id_autor));
      for (const idAutor of idsAutores) if (!autoresActuales.includes(String(idAutor))) await LibroModel.asociarAutor(id, idAutor);
      for (const idAutor of autoresActuales) if (!idsAutores.includes(idAutor)) await LibroModel.desasociarAutor(id, idAutor);

      // Resincroniza generos del libro
      const generosActuales = (await LibroModel.listarGenerosPorLibro(id)).map((g) => String(g.id_genero));
      for (const idGenero of idsGeneros) if (!generosActuales.includes(String(idGenero))) await LibroModel.asociarGenero(id, idGenero);
      for (const idGenero of generosActuales) if (!idsGeneros.includes(idGenero)) await LibroModel.desasociarGenero(id, idGenero);

      res.redirect(`/libros/${id}`);
    } catch (err) {
      res.redirect(`/libros/${id}/editar`);
    }
  },

  async eliminar(req, res) {
    await LibroModel.eliminar(req.params.id);
    res.redirect('/libros');
  },

  // ---- imagenes ----
  async subirImagen(req, res) {
    const { id } = req.params;
    if (!req.file) {
      req.session.mensajeError = 'Selecciona un archivo de imagen valido.';
      return res.redirect(`/libros/${id}`);
    }
    const urlPublica = `/uploads/${req.file.filename}`;
    const esPortada = req.body.es_portada === 'on';
    await LibroModel.agregarImagen(id, urlPublica, Number(req.body.orden) || 0, esPortada);
    res.redirect(`/libros/${id}`);
  },

  async eliminarImagen(req, res) {
    const { id, idImagen } = req.params;
    const imagenes = await LibroModel.listarImagenesPorLibro(id);
    const imagen = imagenes.find((im) => String(im.id_imagen) === idImagen);
    await LibroModel.eliminarImagen(idImagen);
    if (imagen) {
      const rutaArchivo = path.join(__dirname, '..', '..', 'public', imagen.url_imagen);
      fs.unlink(rutaArchivo, () => {});
    }
    res.redirect(`/libros/${id}`);
  },

  // ---- conceptos definidos por libro ----
  async definirConcepto(req, res) {
    const { id } = req.params;
    const { id_concepto, definicion } = req.body;
    if (id_concepto && definicion && definicion.trim()) {
      await LibroModel.definirConcepto(id, id_concepto, definicion.trim());
    }
    res.redirect(`/libros/${id}`);
  },

  async eliminarConcepto(req, res) {
    const { id, idConcepto } = req.params;
    await LibroModel.eliminarConceptoDeLibro(id, idConcepto);
    res.redirect(`/libros/${id}`);
  }
};

module.exports = LibroController;
