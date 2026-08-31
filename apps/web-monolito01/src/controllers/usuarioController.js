const UsuarioModel = require('../models/usuarioModel');

const UsuarioController = {
  async listar(req, res) {
    const usuarios = await UsuarioModel.listar();
    res.render('usuarios/listar', { usuarios });
  },

  async editar(req, res) {
    const usuario = await UsuarioModel.obtenerPorId(req.params.id);
    if (!usuario) return res.status(404).render('error', { titulo: 'No encontrado', mensaje: 'Usuario no encontrado.' });
    res.render('usuarios/editar', { usuario, error: null });
  },

  async actualizar(req, res) {
    const { id } = req.params;
    const { nombre_usuario, correo, rol } = req.body;
    try {
      // No permitir degradar al unico admin desde este formulario si es
      // el usuario en sesion, para no perder acceso administrativo.
      await UsuarioModel.actualizar(id, { nombreUsuario: nombre_usuario, correo, rol });
      res.redirect(`${res.locals.basePath}/usuarios`);
    } catch (err) {
      const usuario = await UsuarioModel.obtenerPorId(id);
      res.status(400).render('usuarios/editar', { usuario, error: 'No fue posible actualizar: ' + err.message });
    }
  },

  async eliminar(req, res) {
    const { id } = req.params;
    if (String(req.session.usuario.id_usuario) === String(id)) {
      req.session.mensajeError = 'No puedes eliminar tu propia cuenta mientras tienes la sesion activa.';
      return res.redirect(`${res.locals.basePath}/usuarios`);
    }
    await UsuarioModel.eliminar(id);
    res.redirect(`${res.locals.basePath}/usuarios`);
  }
};

module.exports = UsuarioController;
