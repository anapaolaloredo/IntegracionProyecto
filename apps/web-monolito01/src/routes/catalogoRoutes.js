const express = require('express');
const { requerirSesion, requerirAdmin } = require('../middlewares/auth');

// Genera un router CRUD completo para un catalogo simple.
// Lectura: cualquier usuario con sesion. Escritura: solo admin.
function crearCatalogoRoutes(controlador) {
  const router = express.Router();

  router.get('/', requerirSesion, controlador.listar);
  router.get('/nuevo', requerirSesion, requerirAdmin, controlador.mostrarCrear);
  router.post('/', requerirSesion, requerirAdmin, controlador.crear);
  router.get('/:id/editar', requerirSesion, requerirAdmin, controlador.mostrarEditar);
  router.put('/:id', requerirSesion, requerirAdmin, controlador.actualizar);
  router.delete('/:id', requerirSesion, requerirAdmin, controlador.eliminar);

  return router;
}

module.exports = crearCatalogoRoutes;
