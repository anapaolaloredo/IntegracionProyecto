const express = require('express');
const router = express.Router();
const UsuarioController = require('../controllers/usuarioController');
const { requerirSesion, requerirAdmin } = require('../middlewares/auth');

router.use(requerirSesion, requerirAdmin);

router.get('/', UsuarioController.listar);
router.get('/:id/editar', UsuarioController.editar);
router.put('/:id', UsuarioController.actualizar);
router.delete('/:id', UsuarioController.eliminar);

module.exports = router;
