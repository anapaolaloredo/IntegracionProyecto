const express = require('express');
const router = express.Router();
const AuthController = require('../controllers/authController');
const { redirigirSiAutenticado } = require('../middlewares/auth');

router.get('/registro', redirigirSiAutenticado, AuthController.mostrarRegistro);
router.post('/registro', redirigirSiAutenticado, AuthController.registrar);
router.get('/login', redirigirSiAutenticado, AuthController.mostrarLogin);
router.post('/login', redirigirSiAutenticado, AuthController.iniciarSesion);
router.post('/logout', AuthController.cerrarSesion);

module.exports = router;
