require('dotenv').config();
const path = require('path');
const express = require('express');
const session = require('express-session');
const pgSession = require('connect-pg-simple')(session);
const methodOverride = require('method-override');

const pool = require('./config/db');
const { inyectarUsuario } = require('./middlewares/auth');
const rutas = require('./routes');

const app = express();

// ---- Motor de vistas (MVC: Vista) ----
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// ---- Middlewares generales ----
app.use(express.urlencoded({ extended: true })); // parseo de formularios HTML (no JSON/API)
app.use(methodOverride('_method'));               // permite PUT/DELETE desde <form>
app.use(express.static(path.join(__dirname, '..', 'public')));

app.use(session({
  store: new pgSession({ pool, tableName: 'session', createTableIfMissing: true }),
  secret: process.env.SESSION_SECRET || 'cambia-esta-clave-por-una-segura',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 1000 * 60 * 60 * 8 } // 8 horas
}));

app.use(inyectarUsuario);

// ---- Rutas (MVC: Controlador) ----
app.use('/', rutas);

// ---- 404 ----
app.use((req, res) => {
  res.status(404).render('error', { titulo: 'Pagina no encontrada', mensaje: 'La ruta solicitada no existe.' });
});

// ---- Manejador de errores ----
app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).render('error', {
    titulo: 'Error interno',
    mensaje: process.env.NODE_ENV === 'production' ? 'Ocurrio un error inesperado.' : err.message
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Servidor de la libreria en linea escuchando en http://localhost:${PORT}`);
});
