const express = require('express');
const router = express.Router();

const { requerirSesion } = require('../middlewares/auth');
const crearCatalogoRoutes = require('./catalogoRoutes');
const crearCatalogoController = require('../controllers/catalogoController');
const { FormatoModel, GeneroModel, AutorModel, ConceptoModel } = require('../models/catalogoModel');

router.get('/', requerirSesion, (req, res) => res.redirect(`${res.locals.basePath}/libros`));

router.use('/auth', require('./auth'));
router.use('/libros', require('./libros'));
router.use('/usuarios', require('./usuarios'));

router.use('/formatos', crearCatalogoRoutes(
  crearCatalogoController(FormatoModel, 'formatos', 'nombre_formato', 'formato')
));
router.use('/generos', crearCatalogoRoutes(
  crearCatalogoController(GeneroModel, 'generos', 'nombre_genero', 'genero')
));
router.use('/autores', crearCatalogoRoutes(
  crearCatalogoController(AutorModel, 'autores', 'nombre_autor', 'autor')
));
router.use('/conceptos', crearCatalogoRoutes(
  crearCatalogoController(ConceptoModel, 'conceptos', 'nombre_concepto', 'concepto')
));

module.exports = router;
