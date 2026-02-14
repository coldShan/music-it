#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OMR_DIR="$ROOT_DIR/apps/omr-service"
WEB_DIR="$ROOT_DIR/apps/web"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
API_HOST="${API_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-5173}"
API_PORT="${API_PORT:-8000}"
AUTO_PORT="${AUTO_PORT:-1}"

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_bin pnpm
require_bin python3

port_in_use() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

next_free_port() {
  local candidate="$1"
  while port_in_use "$candidate"; do
    candidate=$((candidate + 1))
  done
  echo "$candidate"
}

if port_in_use "$WEB_PORT"; then
  if [ "$AUTO_PORT" = "1" ]; then
    OLD_WEB_PORT="$WEB_PORT"
    WEB_PORT="$(next_free_port "$WEB_PORT")"
    echo "Port $OLD_WEB_PORT is busy; frontend moved to $WEB_PORT"
  else
    echo "Frontend port $WEB_PORT is busy. Set WEB_PORT to another value." >&2
    exit 1
  fi
fi

if port_in_use "$API_PORT"; then
  if [ "$AUTO_PORT" = "1" ]; then
    OLD_API_PORT="$API_PORT"
    API_PORT="$(next_free_port "$API_PORT")"
    echo "Port $OLD_API_PORT is busy; backend moved to $API_PORT"
  else
    echo "Backend port $API_PORT is busy. Set API_PORT to another value." >&2
    exit 1
  fi
fi

if ! command -v java >/dev/null 2>&1; then
  echo "Warning: java is not installed. Audiveris may not run." >&2
fi

if [ -z "${AUDIVERIS_CMD:-}" ]; then
  if command -v audiveris >/dev/null 2>&1; then
    AUDIVERIS_CMD="audiveris"
  elif [ -x "/Applications/Audiveris.app/Contents/MacOS/Audiveris" ]; then
    AUDIVERIS_CMD="/Applications/Audiveris.app/Contents/MacOS/Audiveris"
    echo "Using Audiveris app bundle command: $AUDIVERIS_CMD"
  fi
fi

if [ -n "${AUDIVERIS_CMD:-}" ]; then
  export AUDIVERIS_CMD
else
  echo "Warning: audiveris command not found. Set AUDIVERIS_CMD or install Audiveris." >&2
fi

if [ ! -d "$OMR_DIR/.venv" ]; then
  echo "Creating backend virtual environment..."
  python3 -m venv "$OMR_DIR/.venv"
fi

source "$OMR_DIR/.venv/bin/activate"
pip install -q -r "$OMR_DIR/requirements.txt"

cleanup() {
  if [ -n "${BACK_PID:-}" ]; then
    kill "$BACK_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "${WEB_PID:-}" ]; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Backend URL: http://localhost:$API_PORT"
echo "Frontend URL: http://localhost:$WEB_PORT"

(
  cd "$OMR_DIR"
  source .venv/bin/activate
  uvicorn src.main:app --host "$API_HOST" --port "$API_PORT" --reload
) &
BACK_PID=$!

(
  cd "$ROOT_DIR"
  pnpm install --filter @music-it/web
  VITE_OMR_API_URL="http://localhost:$API_PORT" pnpm --filter @music-it/web dev --host "$WEB_HOST" --port "$WEB_PORT"
) &
WEB_PID=$!

wait "$BACK_PID" "$WEB_PID"
