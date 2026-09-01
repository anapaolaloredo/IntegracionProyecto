const pool = require('../config/db');

const LibroModel = {
  async crear({ isbn, titulo, anio, precio, stock, idFormato }) {
    const { rows } = await pool.query(
      'SELECT fn_crear_libro($1,$2,$3,$4,$5,$6) AS id_libro',
      [isbn, titulo, anio, precio, stock, idFormato]
    );
    return rows[0].id_libro;
  },

  async obtenerPorId(id) {
    const { rows } = await pool.query('SELECT * FROM fn_obtener_libro($1)', [id]);
    return rows[0] || null;
  },

  async listar() {
    const { rows } = await pool.query('SELECT * FROM fn_listar_libros()');
    return rows;
  },

  // Listado enriquecido para el catalogo (con nombre de formato, autores y generos).
  // busqueda: texto opcional que filtra por ISBN exacto o titulo parcial (RF-05).
  // El JOIN/STRING_AGG vive centralizado en vista_catalogo_libros (library_views.sql).
  async listarConDetalle(busqueda) {
    const termino = busqueda && busqueda.trim() ? busqueda.trim() : null;
    const { rows } = await pool.query(`
      SELECT * FROM vista_catalogo_libros
      WHERE $1::text IS NULL OR isbn = $1 OR titulo ILIKE '%' || $1 || '%'
      ORDER BY titulo
    `, [termino]);
    return rows;
  },

  async actualizar(id, { titulo, anio, precio, stock, idFormato }) {
    const { rows } = await pool.query(
      'SELECT fn_actualizar_libro($1,$2,$3,$4,$5,$6) AS ok',
      [id, titulo, anio, precio, stock, idFormato]
    );
    return rows[0].ok;
  },

  async eliminar(id) {
    const { rows } = await pool.query('SELECT fn_eliminar_libro($1) AS ok', [id]);
    return rows[0].ok;
  },

  // ---- relacion N:M con autores ----
  async asociarAutor(idLibro, idAutor) {
    await pool.query('SELECT fn_asociar_autor($1,$2)', [idLibro, idAutor]);
  },
  async listarAutoresPorLibro(idLibro) {
    const { rows } = await pool.query('SELECT * FROM fn_listar_autores_por_libro($1)', [idLibro]);
    return rows;
  },
  async desasociarAutor(idLibro, idAutor) {
    await pool.query('SELECT fn_desasociar_autor($1,$2)', [idLibro, idAutor]);
  },

  // ---- relacion N:M con generos ----
  async asociarGenero(idLibro, idGenero) {
    await pool.query('SELECT fn_asociar_genero($1,$2)', [idLibro, idGenero]);
  },
  async listarGenerosPorLibro(idLibro) {
    const { rows } = await pool.query('SELECT * FROM fn_listar_generos_por_libro($1)', [idLibro]);
    return rows;
  },
  async desasociarGenero(idLibro, idGenero) {
    await pool.query('SELECT fn_desasociar_genero($1,$2)', [idLibro, idGenero]);
  },

  // ---- conceptos definidos por libro (atributo propio: definicion) ----
  async definirConcepto(idLibro, idConcepto, definicion) {
    await pool.query('SELECT fn_definir_concepto($1,$2,$3)', [idLibro, idConcepto, definicion]);
  },
  async listarConceptosPorLibro(idLibro) {
    const { rows } = await pool.query('SELECT * FROM fn_listar_conceptos_por_libro($1)', [idLibro]);
    return rows;
  },
  async eliminarConceptoDeLibro(idLibro, idConcepto) {
    await pool.query('SELECT fn_eliminar_concepto_de_libro($1,$2)', [idLibro, idConcepto]);
  },

  // ---- imagenes ----
  async agregarImagen(idLibro, url, orden = 0, esPortada = false, textoAlternativo = '') {
    const { rows } = await pool.query(
      'SELECT fn_agregar_imagen($1,$2,$3,$4,$5) AS id_imagen',
      [idLibro, url, orden, esPortada, textoAlternativo]
    );
    return rows[0].id_imagen;
  },
  async listarImagenesPorLibro(idLibro) {
    const { rows } = await pool.query('SELECT * FROM fn_listar_imagenes_por_libro($1)', [idLibro]);
    return rows;
  },
  async actualizarImagen(idImagen, url, orden) {
    const { rows } = await pool.query(
      'SELECT fn_actualizar_imagen($1,$2,$3) AS ok',
      [idImagen, url, orden]
    );
    return rows[0].ok;
  },
  async eliminarImagen(idImagen) {
    const { rows } = await pool.query('SELECT fn_eliminar_imagen($1) AS ok', [idImagen]);
    return rows[0].ok;
  }
};

module.exports = LibroModel;
