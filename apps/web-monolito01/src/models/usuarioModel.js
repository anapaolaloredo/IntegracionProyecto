const pool = require('../config/db');

const UsuarioModel = {
  async crear({ nombreUsuario, correo, contrasenaHash, rol = 'cliente' }) {
    const { rows } = await pool.query(
      'SELECT fn_crear_usuario($1,$2,$3,$4) AS id_usuario',
      [nombreUsuario, correo, contrasenaHash, rol]
    );
    return rows[0].id_usuario;
  },

  async obtenerPorId(id) {
    const { rows } = await pool.query('SELECT * FROM fn_obtener_usuario($1)', [id]);
    return rows[0] || null;
  },

  async obtenerPorCorreo(correo) {
    const { rows } = await pool.query(
      'SELECT * FROM usuarios WHERE correo = $1',
      [correo]
    );
    return rows[0] || null;
  },

  async obtenerPorNombreUsuario(nombreUsuario) {
    const { rows } = await pool.query(
      'SELECT * FROM usuarios WHERE nombre_usuario = $1',
      [nombreUsuario]
    );
    return rows[0] || null;
  },

  async listar() {
    const { rows } = await pool.query('SELECT * FROM fn_listar_usuarios()');
    return rows;
  },

  async actualizar(id, { nombreUsuario, correo, rol }) {
    const { rows } = await pool.query(
      'SELECT fn_actualizar_usuario($1,$2,$3,$4) AS ok',
      [id, nombreUsuario, correo, rol]
    );
    return rows[0].ok;
  },

  async eliminar(id) {
    const { rows } = await pool.query('SELECT fn_eliminar_usuario($1) AS ok', [id]);
    return rows[0].ok;
  },

  async existeAdmin() {
    const { rows } = await pool.query(
      "SELECT 1 FROM usuarios WHERE rol = 'admin' LIMIT 1"
    );
    return rows.length > 0;
  }
};

module.exports = UsuarioModel;
