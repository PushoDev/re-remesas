#!/usr/bin/env bash
# Arranca el entorno de desarrollo de Re & Re: Postgres (lerd-postgres),
# backend (Django) y frontend (Vite). Pensado para retomar el desarrollo
# rápido, no para producción ni para el entregable.
#
# Uso: ./dev.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

echo "== Re & Re — entorno de desarrollo =="

# 1. Postgres (contenedor compartido de Lerd)
if podman ps --format '{{.Names}}' | grep -qx 'lerd-postgres'; then
  echo "[db]       lerd-postgres ya está corriendo."
elif podman ps -a --format '{{.Names}}' | grep -qx 'lerd-postgres'; then
  echo "[db]       iniciando lerd-postgres..."
  podman start lerd-postgres >/dev/null
else
  echo "[db]       ERROR: no existe el contenedor 'lerd-postgres'. Revisar Lerd." >&2
  exit 1
fi

# 2. Backend (Django) en 0.0.0.0:8001
if ss -tln 2>/dev/null | grep -q ':8001 '; then
  echo "[backend]  ya hay algo escuchando en :8001, no lo vuelvo a arrancar."
else
  echo "[backend]  arrancando Django en 0.0.0.0:8001..."
  (
    cd "$ROOT/backend"
    source venv/bin/activate
    nohup python manage.py runserver 0.0.0.0:8001 > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOG_DIR/backend.pid"
  )
fi

# 3. Frontend (Vite) en 0.0.0.0:5173
if ss -tln 2>/dev/null | grep -q ':5173 '; then
  echo "[frontend] ya hay algo escuchando en :5173, no lo vuelvo a arrancar."
else
  echo "[frontend] arrancando Vite en 0.0.0.0:5173..."
  (
    cd "$ROOT/frontend"
    nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$LOG_DIR/frontend.pid"
  )
fi

sleep 1
cat <<EOF

Listo:
  Frontend  -> https://re-re.test        (o http://localhost:5173)
  Backend   -> https://re-re-api.test/api/health/   (o http://localhost:8001/api/health/)

Logs: $LOG_DIR/backend.log  $LOG_DIR/frontend.log
Para detener:   fuser -k 8001/tcp 5173/tcp
Para reiniciar: fuser -k 8001/tcp 5173/tcp ; ./dev.sh
EOF
