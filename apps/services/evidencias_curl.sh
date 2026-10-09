#!/usr/bin/env bash
# Evidencias con curl de TODOS los endpoints de los seis microservicios.
# Muestra cada peticion (comando) y su respuesta (status, cabeceras y cuerpo) y
# lo guarda en evidencias_<fecha>.txt. Los JWT no se imprimen completos: se
# escriben como $ADMIN / $CLIENTE / $REFRESH_* y se enmascaran en la respuesta.
#
# Uso (en la instancia, con los 6 servicios arriba):
#   cd apps/services && ./evidencias_curl.sh
# Variables opcionales: HOST (localhost), ADMIN_EMAIL, ADMIN_PASS.
# Pide UN solo codigo 2FA, el del admin (se lee del buzon: `mail`, correo mas reciente).
set -u
cd "$(dirname "$0")"
HOST="${HOST:-localhost}"
SALIDA="evidencias_$(date +%Y%m%d_%H%M%S).txt"
PY="login/.venv/bin/python"
exec > >(tee "$SALIDA") 2>&1

L="http://$HOST:5000"; S="http://$HOST:5001"; U="http://$HOST:5002"
A="http://$HOST:5003"; P="http://$HOST:5004"; G="http://$HOST:5005"
JSON='Content-Type: application/json'

# --- utilidades -------------------------------------------------------------
mask() { sed -E 's/("(session_token|refresh_token)": ?")[^"]{12}[^"]*"/\1\2...(JWT enmascarado)"/g; s/(<(session_token|refresh_token)>)[^<]{12}[^<]*/\1(JWT enmascarado)/g'; }
seccion() { printf '\n\n############################################################\n# %s\n############################################################\n' "$1"; }
LAST=""
# req "titulo" "comando mostrado" -- args de curl
req() {
  local titulo="$1" mostrado="$2"; shift 2
  printf '\n--- %s\n$ %s\n' "$titulo" "$mostrado"
  LAST=$(curl -sS -i "$@" 2>&1)
  printf '%s\n' "$LAST" | tr -d '\r' | mask
}
cuerpo() { printf '%s' "$LAST" | tr -d '\r' | sed '1,/^$/d'; }
json() { cuerpo | "$PY" -c "import sys,json
try: print(json.load(sys.stdin)$1)
except Exception: print('')"; }
xml()  { cuerpo | sed -n "s:.*<$1>\\([^<]*\\)</$1>.*:\\1:p" | head -1; }

echo "Evidencias generadas $(date -Is) contra $HOST"

# --- credenciales -----------------------------------------------------------
STAMP=$(date +%s)
C_EMAIL="cliente$STAMP@correo.test"; C_PASS="Cliente-$STAMP-pw"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"; ADMIN_PASS="${ADMIN_PASS:-}"
[ -n "$ADMIN_EMAIL" ] || read -r -p "Correo del admin: " ADMIN_EMAIL
[ -n "$ADMIN_PASS" ] || { read -rs -p "Contrasena del admin: " ADMIN_PASS; echo; }

# ============================================================================
seccion "0. SALUD (publico, sin JWT)"
for par in "login:$L" "books:$S" "users:$U" "authors:$A" "pedidos:$P" "pagos:$G"; do
  req "GET /health ${par%%:*}" "curl -i ${par#*:}/health" "${par#*:}/health"
done

# ============================================================================
seccion "1. LOGIN: registro, 2FA, sesion, extend, refresh"
req "POST /register (cliente nuevo)" "curl -i -X POST $L/register?format=json -H '$JSON' -d '{...}'" \
  -X POST "$L/register?format=json" -H "$JSON" \
  -d "{\"nombre\":\"Cliente\",\"apellido_paterno\":\"Prueba\",\"apellido_materno\":\"Evidencia\",\"email\":\"$C_EMAIL\",\"password\":\"$C_PASS\"}"
ID_CLIENTE=$(json "['id_usuario']")
req "POST /register con correo repetido (409)" "curl -i -X POST $L/register?format=json ..." \
  -X POST "$L/register?format=json" -H "$JSON" \
  -d "{\"nombre\":\"Cliente\",\"apellido_paterno\":\"Prueba\",\"apellido_materno\":\"Evidencia\",\"email\":\"$C_EMAIL\",\"password\":\"$C_PASS\"}"
req "POST /login con contrasena incorrecta (401)" "curl -i -X POST $L/login?format=json ..." \
  -X POST "$L/login?format=json" -H "$JSON" -d "{\"email\":\"$C_EMAIL\",\"password\":\"mal\"}"

login_2fa() {  # $1=email $2=pass $3=nombre -> deja ACCESS y REFRESH
  req "POST /login ($3): envia el codigo 2FA" "curl -i -X POST $L/login?format=json -H '$JSON' -d '{\"email\":\"$1\",\"password\":\"***\"}'" \
    -X POST "$L/login?format=json" -H "$JSON" -d "{\"email\":\"$1\",\"password\":\"$2\"}"
  cuerpo | grep -q '"pendiente_verificacion":true' || { echo "ERROR: el login de $1 fue rechazado (credenciales invalidas), no se envio ningun codigo 2FA. Revisa correo y contrasena."; exit 1; }
  read -r -p ">> Codigo 2FA de $1 (lee el buzon con: mail): " CODIGO
  req "POST /login/verify ($3): emite JWT de acceso (30 min) y refresh (7 dias)" "curl -i -X POST $L/login/verify?format=json -H '$JSON' -d '{\"email\":\"$1\",\"codigo\":\"******\"}'" \
    -X POST "$L/login/verify?format=json" -H "$JSON" -d "{\"email\":\"$1\",\"codigo\":\"$CODIGO\"}"
  ACCESS=$(json "['session_token']"); REFRESH=$(json "['refresh_token']")
}
login_2fa "$ADMIN_EMAIL" "$ADMIN_PASS" "admin"; ADMIN="$ACCESS"; REFRESH_ADMIN="$REFRESH"
[ -n "$ADMIN" ] || { echo "ERROR: no se obtuvo el token del admin; el codigo 2FA es el del correo NUEVO de $ADMIN_EMAIL."; exit 1; }
AH="Authorization: Bearer $ADMIN"

# Solo el admin pasa por el 2FA. Para las pruebas de rol 'cliente' se firma un JWT de
# acceso (role_id=2, 30 min) del cliente registrado arriba con la clave compartida del .env.
SECRETO=$(grep -E '^(JWT_SECRET_KEY|SECRET_KEY)=' users/.env | head -1 | cut -d= -f2-)
CLIENTE=$(JWT_SECRET_KEY="$SECRETO" PYTHONPATH=. "$PY" -c "import sys;from common.jwt_auth import crear_token;print(crear_token(int(sys.argv[1]),2,'access',1800))" "$ID_CLIENTE")
unset SECRETO
CH="Authorization: Bearer $CLIENTE"
echo
echo "(JWT de cliente id=$ID_CLIENTE, role_id=2, firmado localmente con la clave compartida: se usa solo para las pruebas de rol/propiedad; el 2FA real se hizo con el admin)"

req "GET /session (token valido)" 'curl -i -H "Authorization: Bearer $ADMIN" '"$L/session?format=json" -H "$AH" "$L/session?format=json"
req "GET /session sin token (401)" "curl -i $L/session?format=json" "$L/session?format=json"
req "POST /session/extend (emite token nuevo y revoca el anterior)" 'curl -i -X POST -H "Authorization: Bearer $ADMIN" '"$L/session/extend?format=json" -X POST -H "$AH" "$L/session/extend?format=json"
NUEVO=$(json "['session_token']"); [ -n "$NUEVO" ] && { VIEJO="$ADMIN"; ADMIN="$NUEVO"; AH="Authorization: Bearer $ADMIN"; }
req "El token anterior ya no sirve tras extend (401 revocado)" 'curl -i -H "Authorization: Bearer $ADMIN_VIEJO" '"$L/session?format=json" -H "Authorization: Bearer ${VIEJO:-x}" "$L/session?format=json"
req "POST /session/refresh (refresh token -> acceso nuevo)" "curl -i -X POST $L/session/refresh?format=json -H '$JSON' -d '{\"refresh_token\":\"\$REFRESH_ADMIN\"}'" \
  -X POST "$L/session/refresh?format=json" -H "$JSON" -d "{\"refresh_token\":\"$REFRESH_ADMIN\"}"
NUEVO=$(json "['session_token']"); [ -n "$NUEVO" ] && { ADMIN="$NUEVO"; AH="Authorization: Bearer $ADMIN"; }
req "Un token de acceso NO sirve como refresh (401)" "curl -i -X POST $L/session/refresh?format=json -d '{\"refresh_token\":\"\$ADMIN\"}'" \
  -X POST "$L/session/refresh?format=json" -H "$JSON" -d "{\"refresh_token\":\"$ADMIN\"}"

# ============================================================================
seccion "2. USERS (5002)"
req "GET /api/roles (publico)" "curl -i $U/api/roles" "$U/api/roles"
req "GET /api/users sin token (401)" "curl -i $U/api/users" "$U/api/users"
req "GET /api/users como cliente (403)" 'curl -i -H "Authorization: Bearer $CLIENTE" '"$U/api/users" -H "$CH" "$U/api/users"
req "GET /api/users como admin (200)" 'curl -i -H "Authorization: Bearer $ADMIN" '"$U/api/users" -H "$AH" "$U/api/users"
ID_CLIENTE=$(cuerpo | "$PY" -c "import sys,json;print(next((u['id_usuario'] for u in json.load(sys.stdin) if u.get('correo')=='$C_EMAIL'),''))")
echo "(id del cliente registrado: $ID_CLIENTE)"
req "GET /api/users/{id} propio" "curl -i -H 'Authorization: Bearer \$CLIENTE' $U/api/users/$ID_CLIENTE" -H "$CH" "$U/api/users/$ID_CLIENTE"
req "GET /api/users/1 ajeno como cliente (403)" "curl -i -H 'Authorization: Bearer \$CLIENTE' $U/api/users/1" -H "$CH" "$U/api/users/1"
req "PATCH /api/users/{id} (actualiza nombre propio)" "curl -i -X PATCH -H 'Authorization: Bearer \$CLIENTE' $U/api/users/$ID_CLIENTE -d '{\"nombre\":\"Cliente Editado\"}'" \
  -X PATCH -H "$CH" -H "$JSON" -d '{"nombre":"Cliente Editado"}' "$U/api/users/$ID_CLIENTE"
req "PUT /api/users/{id} sin campos obligatorios (400)" "curl -i -X PUT ... -d '{\"nombre\":\"X\"}'" \
  -X PUT -H "$CH" -H "$JSON" -d '{"nombre":"X"}' "$U/api/users/$ID_CLIENTE"
req "PATCH /api/users/{id}/password (propio, exige password_actual)" "curl -i -X PATCH ... -d '{\"password_actual\":\"***\",\"password_nueva\":\"***\"}'" \
  -X PATCH -H "$CH" -H "$JSON" -d "{\"password_actual\":\"$C_PASS\",\"password_nueva\":\"NuevaClave-$STAMP\"}" "$U/api/users/$ID_CLIENTE/password"
req "POST /api/users como cliente (403)" "curl -i -X POST -H 'Authorization: Bearer \$CLIENTE' $U/api/users" -X POST -H "$CH" -H "$JSON" -d '{}' "$U/api/users"
EXTRA="extra$STAMP@correo.test"
req "POST /api/users como admin (201)" "curl -i -X POST -H 'Authorization: Bearer \$ADMIN' $U/api/users -d '{...}'" \
  -X POST -H "$AH" -H "$JSON" -d "{\"correo\":\"$EXTRA\",\"nombre\":\"Extra\",\"apellido_paterno\":\"Uno\",\"apellido_materno\":\"Dos\",\"password\":\"ClaveExtra-$STAMP\",\"rol\":\"cliente\"}" "$U/api/users"
ID_EXTRA=$(json "['id_usuario']")
req "PATCH /api/users/{id}/rol (admin)" "curl -i -X PATCH -H 'Authorization: Bearer \$ADMIN' $U/api/users/$ID_EXTRA/rol -d '{\"rol\":\"cliente\"}'" \
  -X PATCH -H "$AH" -H "$JSON" -d '{"rol":"cliente"}' "$U/api/users/$ID_EXTRA/rol"
req "PATCH rol invalido (400)" "curl -i -X PATCH ... -d '{\"rol\":\"root\"}'" -X PATCH -H "$AH" -H "$JSON" -d '{"rol":"root"}' "$U/api/users/$ID_EXTRA/rol"
req "DELETE /api/users/{id} como cliente (403)" "curl -i -X DELETE -H 'Authorization: Bearer \$CLIENTE' $U/api/users/$ID_EXTRA" -X DELETE -H "$CH" "$U/api/users/$ID_EXTRA"
req "DELETE /api/users/{id} como admin (200)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $U/api/users/$ID_EXTRA" -X DELETE -H "$AH" "$U/api/users/$ID_EXTRA"
req "DELETE de nuevo (404)" "curl -i -X DELETE ... $U/api/users/$ID_EXTRA" -X DELETE -H "$AH" "$U/api/users/$ID_EXTRA"

# ============================================================================
seccion "3. SOAP / LIBROS (5001, respuestas XML) + cache Redis"
ISBN="978-EVID-$STAMP"
req "GET /api/libros (publico; 1a vez llena el cache books:list:*)" "curl -i $S/api/libros" "$S/api/libros"
req "GET /api/libros/buscar?titulo=a" "curl -i '$S/api/libros/buscar?titulo=a'" "$S/api/libros/buscar?titulo=a"
req "GET /api/libros/temas" "curl -i $S/api/libros/temas" "$S/api/libros/temas"
req "GET /api/libros/catalogo" "curl -i $S/api/libros/catalogo" "$S/api/libros/catalogo"
req "POST /api/libros sin token (401)" "curl -i -X POST $S/api/libros" -X POST -H "$JSON" -d '{}' "$S/api/libros"
req "POST /api/libros como cliente (403, solo admin)" "curl -i -X POST -H 'Authorization: Bearer \$CLIENTE' $S/api/libros" -X POST -H "$CH" -H "$JSON" -d '{}' "$S/api/libros"
req "POST /api/libros admin con campos faltantes (400)" "curl -i -X POST -H 'Authorization: Bearer \$ADMIN' $S/api/libros -d '{\"isbn\":\"x\"}'" -X POST -H "$AH" -H "$JSON" -d '{"isbn":"x"}' "$S/api/libros"
req "POST /api/libros admin (201): invalida el cache" "curl -i -X POST -H 'Authorization: Bearer \$ADMIN' $S/api/libros -d '{...}'" \
  -X POST -H "$AH" -H "$JSON" -d "{\"isbn\":\"$ISBN\",\"title\":\"Libro de evidencias\",\"publicationYear\":2026,\"price\":199.5,\"stock\":10,\"format\":\"Tapa dura\",\"authors\":[\"Autor Evidencia\"],\"genres\":[\"Pruebas\"]}" "$S/api/libros"
req "POST con ISBN repetido (409)" "curl -i -X POST ... (mismo isbn)" -X POST -H "$AH" -H "$JSON" -d "{\"isbn\":\"$ISBN\",\"title\":\"X\",\"price\":1,\"stock\":1,\"format\":\"Tapa dura\"}" "$S/api/libros"
req "GET /api/libros/{isbn} (1a vez: MISS)" "curl -i $S/api/libros/$ISBN" "$S/api/libros/$ISBN"
req "GET /api/libros/{isbn} (2a vez: sale del cache books:{isbn})" "curl -i $S/api/libros/$ISBN" "$S/api/libros/$ISBN"
req "GET /api/libros/inexistente (404)" "curl -i $S/api/libros/no-existe" "$S/api/libros/no-existe"
req "PUT /api/libros/{isbn} cualquier JWT valido (200): invalida el cache" "curl -i -X PUT -H 'Authorization: Bearer \$CLIENTE' $S/api/libros/$ISBN -d '{\"stock\":20}'" \
  -X PUT -H "$CH" -H "$JSON" -d '{"stock":20}' "$S/api/libros/$ISBN"
req "GET tras el PUT (stock nuevo, cache invalidado)" "curl -i $S/api/libros/$ISBN" "$S/api/libros/$ISBN"

# id_libro numerico (lo necesitan authors y pedidos); sale de la base
ID_LIBRO=""
if command -v psql >/dev/null && [ -f soap/.env ]; then
  DBPW=$(grep -E '^DB_PASSWORD=' soap/.env | cut -d= -f2-)
  ID_LIBRO=$(PGPASSWORD="$DBPW" psql -h localhost -U library_user -d library -Atc "SELECT id_libro FROM libros WHERE isbn='$ISBN'" 2>/dev/null)
  unset DBPW
fi
[ -n "$ID_LIBRO" ] || read -r -p ">> id_libro de $ISBN (psql: SELECT id_libro FROM libros WHERE isbn='$ISBN';): " ID_LIBRO
echo "(id_libro de $ISBN: $ID_LIBRO)"

# ============================================================================
seccion "4. AUTHORS (5003)"
req "GET /api/authors (publico)" "curl -i $A/api/authors" "$A/api/authors"
req "POST /api/authors sin token (401)" "curl -i -X POST $A/api/authors" -X POST -H "$JSON" -d '{}' "$A/api/authors"
req "POST /api/authors como cliente (403)" "curl -i -X POST -H 'Authorization: Bearer \$CLIENTE' $A/api/authors" -X POST -H "$CH" -H "$JSON" -d '{"nombre_autor":"X"}' "$A/api/authors"
req "POST /api/authors admin (201)" "curl -i -X POST -H 'Authorization: Bearer \$ADMIN' $A/api/authors -d '{\"nombre_autor\":\"Autor API $STAMP\"}'" \
  -X POST -H "$AH" -H "$JSON" -d "{\"nombre_autor\":\"Autor API $STAMP\"}" "$A/api/authors"
ID_AUTOR=$(json "['id_autor']")
req "POST nombre repetido (409)" "curl -i -X POST ... (mismo nombre)" -X POST -H "$AH" -H "$JSON" -d "{\"nombre_autor\":\"Autor API $STAMP\"}" "$A/api/authors"
req "POST nombre vacio (400)" "curl -i -X POST ... -d '{\"nombre_autor\":\"\"}'" -X POST -H "$AH" -H "$JSON" -d '{"nombre_autor":""}' "$A/api/authors"
req "GET /api/authors/{id} (publico, con libros)" "curl -i $A/api/authors/$ID_AUTOR" "$A/api/authors/$ID_AUTOR"
req "PATCH /api/authors/{id} (renombra)" "curl -i -X PATCH -H 'Authorization: Bearer \$ADMIN' $A/api/authors/$ID_AUTOR -d '{\"nombre_autor\":\"Autor Renombrado $STAMP\"}'" \
  -X PATCH -H "$AH" -H "$JSON" -d "{\"nombre_autor\":\"Autor Renombrado $STAMP\"}" "$A/api/authors/$ID_AUTOR"
req "POST /api/authors/{id}/books (vincula libro)" "curl -i -X POST -H 'Authorization: Bearer \$ADMIN' $A/api/authors/$ID_AUTOR/books -d '{\"id_libro\":$ID_LIBRO}'" \
  -X POST -H "$AH" -H "$JSON" -d "{\"id_libro\":$ID_LIBRO}" "$A/api/authors/$ID_AUTOR/books"
req "DELETE autor con libros (409)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $A/api/authors/$ID_AUTOR" -X DELETE -H "$AH" "$A/api/authors/$ID_AUTOR"
req "DELETE /api/authors/{id}/books/{libro} (desvincula)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $A/api/authors/$ID_AUTOR/books/$ID_LIBRO" -X DELETE -H "$AH" "$A/api/authors/$ID_AUTOR/books/$ID_LIBRO"
req "DELETE /api/authors/{id} (200)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $A/api/authors/$ID_AUTOR" -X DELETE -H "$AH" "$A/api/authors/$ID_AUTOR"

# ============================================================================
seccion "5. PEDIDOS (5004): transaccion con stock"
req "POST /api/pedidos sin token (401)" "curl -i -X POST $P/api/pedidos" -X POST -H "$JSON" -d '{}' "$P/api/pedidos"
req "POST /api/pedidos lineas vacias (400)" "curl -i -X POST ... -d '{\"lineas\":[]}'" -X POST -H "$CH" -H "$JSON" -d '{"lineas":[]}' "$P/api/pedidos"
req "POST /api/pedidos stock insuficiente (409, rollback)" "curl -i -X POST ... -d '{\"lineas\":[{\"id_libro\":$ID_LIBRO,\"cantidad\":9999}]}'" \
  -X POST -H "$CH" -H "$JSON" -d "{\"lineas\":[{\"id_libro\":$ID_LIBRO,\"cantidad\":9999}]}" "$P/api/pedidos"
req "POST /api/pedidos libro inexistente (404)" "curl -i -X POST ... id_libro 999999999" -X POST -H "$CH" -H "$JSON" -d '{"lineas":[{"id_libro":999999999,"cantidad":1}]}' "$P/api/pedidos"
req "POST /api/pedidos (201): descuenta stock 20 -> 17" "curl -i -X POST -H 'Authorization: Bearer \$CLIENTE' $P/api/pedidos -d '{\"lineas\":[{\"id_libro\":$ID_LIBRO,\"cantidad\":3}]}'" \
  -X POST -H "$CH" -H "$JSON" -d "{\"lineas\":[{\"id_libro\":$ID_LIBRO,\"cantidad\":3}]}" "$P/api/pedidos"
PED=$(json "['id_pedido']")
req "GET stock del libro tras el pedido (cache invalidado por pedidos)" "curl -i $S/api/libros/$ISBN" "$S/api/libros/$ISBN"
req "GET /api/pedidos (cliente: solo los suyos)" "curl -i -H 'Authorization: Bearer \$CLIENTE' $P/api/pedidos" -H "$CH" "$P/api/pedidos"
req "GET /api/pedidos (admin: todos)" "curl -i -H 'Authorization: Bearer \$ADMIN' $P/api/pedidos" -H "$AH" "$P/api/pedidos"
req "GET /api/pedidos/{id}" "curl -i -H 'Authorization: Bearer \$CLIENTE' $P/api/pedidos/$PED" -H "$CH" "$P/api/pedidos/$PED"
req "GET /api/pedidos/999999 (404)" "curl -i ... $P/api/pedidos/999999" -H "$CH" "$P/api/pedidos/999999"
req "PATCH estado a enviado como cliente (403/409: solo admin y pagado)" "curl -i -X PATCH ... -d '{\"estado\":\"enviado\"}'" -X PATCH -H "$CH" -H "$JSON" -d '{"estado":"enviado"}' "$P/api/pedidos/$PED/estado"
req "PATCH estado invalido (400)" "curl -i -X PATCH ... -d '{\"estado\":123}'" -X PATCH -H "$CH" -H "$JSON" -d '{"estado":123}' "$P/api/pedidos/$PED/estado"
req "DELETE pedido como cliente (403)" "curl -i -X DELETE -H 'Authorization: Bearer \$CLIENTE' $P/api/pedidos/$PED" -X DELETE -H "$CH" "$P/api/pedidos/$PED"

# ============================================================================
seccion "6. PAGOS (5005): pago -> pedido pagado -> reembolso"
req "POST /api/pagos sin token (401)" "curl -i -X POST $G/api/pagos" -X POST -H "$JSON" -d '{}' "$G/api/pagos"
req "POST /api/pagos metodo invalido (400)" "curl -i -X POST ... -d '{\"id_pedido\":$PED,\"metodo\":\"bitcoin\"}'" -X POST -H "$CH" -H "$JSON" -d "{\"id_pedido\":$PED,\"metodo\":\"bitcoin\"}" "$G/api/pagos"
req "POST /api/pagos monto distinto al total (409)" "curl -i -X POST ... -d '{\"monto\":1}'" -X POST -H "$CH" -H "$JSON" -d "{\"id_pedido\":$PED,\"metodo\":\"tarjeta\",\"monto\":1}" "$G/api/pagos"
req "POST /api/pagos (201): inserta pago y marca el pedido pagado" "curl -i -X POST -H 'Authorization: Bearer \$CLIENTE' $G/api/pagos -d '{\"id_pedido\":$PED,\"metodo\":\"tarjeta\"}'" \
  -X POST -H "$CH" -H "$JSON" -d "{\"id_pedido\":$PED,\"metodo\":\"tarjeta\"}" "$G/api/pagos"
PAGO=$(json "['id_pago']")
req "POST /api/pagos otra vez (409, ya pagado)" "curl -i -X POST ... (mismo pedido)" -X POST -H "$CH" -H "$JSON" -d "{\"id_pedido\":$PED,\"metodo\":\"tarjeta\"}" "$G/api/pagos"
req "GET /api/pedidos/{id} (estado: pagado)" "curl -i ... $P/api/pedidos/$PED" -H "$CH" "$P/api/pedidos/$PED"
req "GET /api/pagos (cliente)" "curl -i -H 'Authorization: Bearer \$CLIENTE' $G/api/pagos" -H "$CH" "$G/api/pagos"
req "GET /api/pagos (admin)" "curl -i -H 'Authorization: Bearer \$ADMIN' $G/api/pagos" -H "$AH" "$G/api/pagos"
req "GET /api/pagos/{id}" "curl -i -H 'Authorization: Bearer \$CLIENTE' $G/api/pagos/$PAGO" -H "$CH" "$G/api/pagos/$PAGO"
req "GET /api/pagos/999999 (404)" "curl -i ... $G/api/pagos/999999" -H "$CH" "$G/api/pagos/999999"
req "DELETE /api/pagos/{id} como cliente (403)" "curl -i -X DELETE -H 'Authorization: Bearer \$CLIENTE' $G/api/pagos/$PAGO" -X DELETE -H "$CH" "$G/api/pagos/$PAGO"
req "PATCH pedido pagado -> enviado (admin)" "curl -i -X PATCH -H 'Authorization: Bearer \$ADMIN' $P/api/pedidos/$PED/estado -d '{\"estado\":\"enviado\"}'" -X PATCH -H "$AH" -H "$JSON" -d '{"estado":"enviado"}' "$P/api/pedidos/$PED/estado"
req "DELETE pago de pedido enviado (409, no reembolsable)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $G/api/pagos/$PAGO" -X DELETE -H "$AH" "$G/api/pagos/$PAGO"

# segundo pedido para probar reembolso y cancelacion
req "POST segundo pedido" "curl -i -X POST ... lineas=[{id_libro:$ID_LIBRO,cantidad:2}]" -X POST -H "$CH" -H "$JSON" -d "{\"lineas\":[{\"id_libro\":$ID_LIBRO,\"cantidad\":2}]}" "$P/api/pedidos"
PED2=$(json "['id_pedido']")
req "Pago del segundo pedido" "curl -i -X POST ... $G/api/pagos" -X POST -H "$CH" -H "$JSON" -d "{\"id_pedido\":$PED2,\"metodo\":\"efectivo\"}" "$G/api/pagos"
PAGO2=$(json "['id_pago']")
req "DELETE /api/pagos/{id} como admin (reembolso: pedido vuelve a pendiente)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $G/api/pagos/$PAGO2" -X DELETE -H "$AH" "$G/api/pagos/$PAGO2"
req "PATCH pedido -> cancelado (devuelve stock)" "curl -i -X PATCH -H 'Authorization: Bearer \$CLIENTE' $P/api/pedidos/$PED2/estado -d '{\"estado\":\"cancelado\"}'" -X PATCH -H "$CH" -H "$JSON" -d '{"estado":"cancelado"}' "$P/api/pedidos/$PED2/estado"
req "DELETE pedido cancelado como admin (200)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $P/api/pedidos/$PED2" -X DELETE -H "$AH" "$P/api/pedidos/$PED2"
req "DELETE pedido enviado (409, no esta cancelado)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $P/api/pedidos/$PED" -X DELETE -H "$AH" "$P/api/pedidos/$PED"

# ============================================================================
seccion "7. SEGURIDAD JWT en cualquier servicio"
req "Token manipulado (firma falsa) -> 401" "curl -i -H 'Authorization: Bearer <JWT con firma alterada>' $U/api/users" -H "Authorization: Bearer ${ADMIN%?}x" "$U/api/users"
req "Refresh token usado como acceso -> 401" "curl -i -H 'Authorization: Bearer \$REFRESH_ADMIN' $U/api/users" -H "Authorization: Bearer $REFRESH_ADMIN" "$U/api/users"
req "Encabezado mal formado -> 401" "curl -i -H 'Authorization: Token abc' $U/api/users" -H "Authorization: Token abc" "$U/api/users"
req "CORS preflight (OPTIONS) desde un cliente web" "curl -i -X OPTIONS -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: POST' $U/api/users" \
  -X OPTIONS -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: authorization,content-type" "$U/api/users"

# ============================================================================
seccion "8. LIMPIEZA y LOGOUT: revocacion en Redis visible en TODOS los servicios"
req "Limpieza: DELETE /api/libros/{isbn} (admin; 409 si tiene pedidos asociados)" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $S/api/libros/$ISBN" -X DELETE -H "$AH" "$S/api/libros/$ISBN"
req "Limpieza: DELETE /api/users/{id} del cliente de prueba" "curl -i -X DELETE -H 'Authorization: Bearer \$ADMIN' $U/api/users/$ID_CLIENTE" -X DELETE -H "$AH" "$U/api/users/$ID_CLIENTE"
req "POST /logout (admin): borra sesion+refresh en Redis y revoca el JWT" 'curl -i -X POST -H "Authorization: Bearer $ADMIN" '"$L/logout?format=json" -X POST -H "$AH" "$L/logout?format=json"
req "El mismo token ya no sirve en users (401)" 'curl -i -H "Authorization: Bearer $ADMIN" '"$U/api/users" -H "$AH" "$U/api/users"
req "... ni en authors al escribir (401)" 'curl -i -X POST -H "Authorization: Bearer $ADMIN" '"$A/api/authors" -X POST -H "$AH" -H "$JSON" -d '{"nombre_autor":"X"}' "$A/api/authors"
req "... ni en pedidos (401)" 'curl -i -H "Authorization: Bearer $ADMIN" '"$P/api/pedidos" -H "$AH" "$P/api/pedidos"
req "... ni en pagos (401)" 'curl -i -H "Authorization: Bearer $ADMIN" '"$G/api/pagos" -H "$AH" "$G/api/pagos"
req "... ni en soap al crear libros (401)" 'curl -i -X POST -H "Authorization: Bearer $ADMIN" '"$S/api/libros" -X POST -H "$AH" -H "$JSON" -d '{}' "$S/api/libros"
req "... ni en login /session (401)" 'curl -i -H "Authorization: Bearer $ADMIN" '"$L/session?format=json" -H "$AH" "$L/session?format=json"
req "El refresh token del admin tambien quedo invalidado (401)" "curl -i -X POST $L/session/refresh?format=json -d '{\"refresh_token\":\"\$REFRESH_ADMIN\"}'" \
  -X POST "$L/session/refresh?format=json" -H "$JSON" -d "{\"refresh_token\":\"$REFRESH_ADMIN\"}"
req "Los endpoints publicos siguen funcionando sin sesion (catalogo, roles, autores, health)" "curl -i $A/api/authors" "$A/api/authors"

seccion "9. METRICAS (despues del trafico: contadores de auth/revocaciones por servicio)"
for par in "login:$L" "users:$U" "pedidos:$P"; do
  req "GET /metrics ${par%%:*}" "curl -i ${par#*:}/metrics" "${par#*:}/metrics"
done

printf '\n\nFIN. Evidencias guardadas en %s\n' "$SALIDA"
