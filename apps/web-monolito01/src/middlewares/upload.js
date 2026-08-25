const multer = require('multer');
const path = require('path');
const fs = require('fs');

const DIR_DESTINO = path.join(__dirname, '..', '..', 'public', 'uploads');
if (!fs.existsSync(DIR_DESTINO)) fs.mkdirSync(DIR_DESTINO, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, DIR_DESTINO),
  filename: (req, file, cb) => {
    const sufijo = Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, sufijo + path.extname(file.originalname).toLowerCase());
  }
});

function filtroImagen(req, file, cb) {
  const permitidos = /jpeg|jpg|png|webp|gif/;
  const extOk = permitidos.test(path.extname(file.originalname).toLowerCase());
  const mimeOk = permitidos.test(file.mimetype);
  if (extOk && mimeOk) return cb(null, true);
  cb(new Error('Solo se permiten imagenes (jpg, jpeg, png, webp, gif).'));
}

const upload = multer({
  storage,
  fileFilter: filtroImagen,
  limits: { fileSize: 5 * 1024 * 1024 } // 5 MB
});

module.exports = upload;
