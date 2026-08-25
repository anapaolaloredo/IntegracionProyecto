const bcrypt = require('bcrypt');
const UsuarioModel = require('../models/usuarioModel');

const RONDAS_SAL = 10;

const AuthController = {
  mostrarRegistro(req, res) {
    res.render('auth/registro', { error: null, valores: {} });
  },

  async registrar(req, res) {
    const { nombre_usuario, correo, contrasena, confirmar_contrasena } = req.body;
    try {
      if (!nombre_usuario || !correo || !contrasena) {
        throw new Error('Todos los campos son obligatorios.');
      }
      if (contrasena !== confirmar_contrasena) {
        throw new Error('Las contrasenas no coinciden.');
      }
      if (contrasena.length < 6) {
        throw new Error('La contrasena debe tener al menos 6 caracteres.');
      }
      const existeCorreo = await UsuarioModel.obtenerPorCorreo(correo);
      if (existeCorreo) throw new Error('Ese correo ya esta registrado.');
      const existeNombre = await UsuarioModel.obtenerPorNombreUsuario(nombre_usuario);
      if (existeNombre) throw new Error('Ese nombre de usuario ya esta en uso.');

      // Regla de negocio: el primer usuario del sistema se vuelve admin;
      // el resto siempre se registra como cliente. La unicidad del admin
      // tambien esta garantizada a nivel de base de datos (indice unico).
      const hayAdmin = await UsuarioModel.existeAdmin();
      const rol = hayAdmin ? 'cliente' : 'admin';

      const hash = await bcrypt.hash(contrasena, RONDAS_SAL);
      const id = await UsuarioModel.crear({
        nombreUsuario: nombre_usuario,
        correo,
        contrasenaHash: hash,
        rol
      });

      req.session.usuario = { id_usuario: id, nombre_usuario, correo, rol };
      res.redirect('/libros');
    } catch (err) {
      res.status(400).render('auth/registro', {
        error: err.message,
        valores: { nombre_usuario, correo }
      });
    }
  },

  mostrarLogin(req, res) {
    const mensaje = req.session.mensajeError;
    req.session.mensajeError = null;
    res.render('auth/login', { error: mensaje || null });
  },

  async iniciarSesion(req, res) {
    const { correo, contrasena } = req.body;
    try {
      const usuario = await UsuarioModel.obtenerPorCorreo(correo);
      if (!usuario) throw new Error('Credenciales invalidas.');
      const ok = await bcrypt.compare(contrasena, usuario.contrasena_hash);
      if (!ok) throw new Error('Credenciales invalidas.');

      req.session.usuario = {
        id_usuario: usuario.id_usuario,
        nombre_usuario: usuario.nombre_usuario,
        correo: usuario.correo,
        rol: usuario.rol
      };
      res.redirect('/libros');
    } catch (err) {
      res.status(401).render('auth/login', { error: err.message });
    }
  },

  cerrarSesion(req, res) {
    req.session.destroy(() => res.redirect('/auth/login'));
  }
};

module.exports = AuthController;
