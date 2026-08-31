// Middlewares de control de acceso basados en sesion de servidor
// (express-session). No se exponen tokens ni endpoints de API.

function inyectarUsuario(req, res, next) {
  res.locals.usuarioActual = req.session.usuario || null;
  next();
}

function requerirSesion(req, res, next) {
  if (!req.session.usuario) {
    req.session.mensajeError = 'Debes iniciar sesion para continuar.';
    return res.redirect(`${res.locals.basePath}/auth/login`);
  }
  next();
}

function requerirAdmin(req, res, next) {
  if (!req.session.usuario || req.session.usuario.rol !== 'admin') {
    return res.status(403).render('error', {
      titulo: 'Acceso denegado',
      mensaje: 'Esta seccion es exclusiva para el administrador del sistema.'
    });
  }
  next();
}

function redirigirSiAutenticado(req, res, next) {
  if (req.session.usuario) {
    return res.redirect(`${res.locals.basePath}/libros`);
  }
  next();
}

module.exports = { inyectarUsuario, requerirSesion, requerirAdmin, redirigirSiAutenticado };
