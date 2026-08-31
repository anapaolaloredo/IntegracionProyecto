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

// Prefijo bajo el que NGINX publica la app (ej. /library). Se usa tanto
// para montar rutas/estaticos como para que las vistas y los redirect()
// generen URLs consistentes con el reverse proxy. Con '' la app funciona
// igual que antes, montada en la raiz (util para pruebas locales).
const BASE_PATH = process.env.BASE_PATH ?? '/library';

// ---- Motor de vistas (MVC: Vista) ----
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Inyecta el prefijo lo antes posible para que este disponible en todas
// las vistas (via res.locals) y en los controladores/middlewares que
// arman res.redirect() con rutas absolutas.
app.use((req, res, next) => {
  res.locals.basePath = BASE_PATH;
  next();
});

// ---- Middlewares generales ----
app.use(express.urlencoded({ extended: true })); // parseo de formularios HTML (no JSON/API)
app.use(methodOverride('_method'));               // permite PUT/DELETE desde <form>
app.use(BASE_PATH, express.static(path.join(__dirname, '..', 'public')));

app.use(session({
  store: new pgSession({ pool, tableName: 'session', createTableIfMissing: true }),
  secret: process.env.SESSION_SECRET || 'cambia-esta-clave-por-una-segura',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 1000 * 60 * 60 * 8, path: BASE_PATH || '/' } // 8 horas
}));

app.use(inyectarUsuario);

// ---- Rutas (MVC: Controlador) ----
app.use(BASE_PATH, rutas);

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
