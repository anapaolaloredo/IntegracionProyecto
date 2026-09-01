const express = require('express');
const router = express.Router();
const LibroController = require('../controllers/libroController');
const { requerirSesion, requerirAdmin } = require('../middlewares/auth');
const upload = require('../middlewares/upload');

router.use(requerirSesion);

router.get('/', LibroController.catalogo);
router.get('/nuevo', requerirAdmin, LibroController.mostrarCrear);
router.post('/', requerirAdmin, LibroController.crear);
router.get('/:id', LibroController.detalle);
router.get('/:id/editar', requerirAdmin, LibroController.mostrarEditar);
router.put('/:id', requerirAdmin, LibroController.actualizar);
router.delete('/:id', requerirAdmin, LibroController.eliminar);

// Imagenes del libro
router.post('/:id/imagenes', requerirAdmin, upload.subirImagenControlado, LibroController.subirImagen);
router.delete('/:id/imagenes/:idImagen', requerirAdmin, LibroController.eliminarImagen);

// Conceptos definidos por el libro (definicion propia de la relacion)
router.post('/:id/conceptos', requerirAdmin, LibroController.definirConcepto);
router.delete('/:id/conceptos/:idConcepto', requerirAdmin, LibroController.eliminarConcepto);

module.exports = router;
