// test/usuarios.test.js
const test = require('node:test');
const assert = require('node:assert');

test('crea un usuario y devuelve un id', async () => {
  const id = await fn_crear_usuario('paola', 'p@x.com', 'hash123');
  assert.ok(id > 0);
});