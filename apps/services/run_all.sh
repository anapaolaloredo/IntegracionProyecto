#!/usr/bin/env bash
# Arranca los seis microservicios a la vez. Ctrl+C los detiene a todos.
#   ./run_all.sh                 # todos
#   ./run_all.sh users pagos     # solo algunos
# Cada servicio usa su propio .venv y su propio .env (cwd = carpeta del servicio).
set -u
cd "$(dirname "$0")"

declare -a TODOS=(login:5000 soap:5001 users:5002 authors:5003 pedidos:5004 pagos:5005)
SELECCION=("$@")
[ ${#SELECCION[@]} -eq 0 ] && SELECCION=(login soap users authors pedidos pagos)

export PYTHONUNBUFFERED=1
trap 'trap - INT TERM; echo; echo "Deteniendo servicios..."; kill 0' INT TERM

arrancados=0
for nombre in "${SELECCION[@]}"; do
  puerto=""
  for par in "${TODOS[@]}"; do [ "${par%%:*}" = "$nombre" ] && puerto="${par##*:}"; done
  if [ -z "$puerto" ]; then echo "Servicio desconocido: $nombre" >&2; continue; fi
  if [ ! -x "$nombre/.venv/bin/python" ]; then
    echo "[$nombre] sin $nombre/.venv (python -m venv .venv && .venv/bin/pip install -r requirements.txt); se omite" >&2
    continue
  fi
  [ -f "$nombre/.env" ] || echo "[$nombre] aviso: no hay $nombre/.env (copia .env.example); puede no arrancar" >&2
  (
    cd "$nombre" && exec .venv/bin/python app.py 2>&1 | awk -v p="[$nombre]" '{print p, $0; fflush()}'
  ) &
  echo "[$nombre] arrancando en el puerto $puerto"
  arrancados=$((arrancados + 1))
done

[ "$arrancados" -eq 0 ] && { echo "No se arranco ningun servicio." >&2; exit 1; }
wait
