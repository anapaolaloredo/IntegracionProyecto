const pool = require('../config/db');

// Fabrica de modelos para los catalogos que comparten la misma forma
// (id, nombre): formatos, generos, autores, conceptos.
function crearCatalogoModel({ crear, listar, actualizar, eliminar }) {
  return {
    async crear(nombre) {
      const { rows } = await pool.query(`SELECT ${crear}($1) AS id`, [nombre]);
      return rows[0].id;
    },
    async listar() {
      const { rows } = await pool.query(`SELECT * FROM ${listar}()`);
      return rows;
    },
    async actualizar(id, nombre) {
      const { rows } = await pool.query(`SELECT ${actualizar}($1,$2) AS ok`, [id, nombre]);
      return rows[0].ok;
    },
    async eliminar(id) {
      const { rows } = await pool.query(`SELECT ${eliminar}($1) AS ok`, [id]);
      return rows[0].ok;
    }
  };
}

const FormatoModel = crearCatalogoModel({
  crear: 'fn_crear_formato',
  listar: 'fn_listar_formatos',
  actualizar: 'fn_actualizar_formato',
  eliminar: 'fn_eliminar_formato'
});

const GeneroModel = crearCatalogoModel({
  crear: 'fn_crear_genero',
  listar: 'fn_listar_generos',
  actualizar: 'fn_actualizar_genero',
  eliminar: 'fn_eliminar_genero'
});

const AutorModel = crearCatalogoModel({
  crear: 'fn_crear_autor',
  listar: 'fn_listar_autores',
  actualizar: 'fn_actualizar_autor',
  eliminar: 'fn_eliminar_autor'
});

const ConceptoModel = crearCatalogoModel({
  crear: 'fn_crear_concepto',
  listar: 'fn_listar_conceptos',
  actualizar: 'fn_actualizar_concepto',
  eliminar: 'fn_eliminar_concepto'
});

module.exports = { FormatoModel, GeneroModel, AutorModel, ConceptoModel };
