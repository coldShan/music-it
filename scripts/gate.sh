#!/usr/bin/env bash
# 门禁：依次运行全部检查，任何一项失败则退出码非 0。
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

failed=()

run() {
  local name="$1"
  shift
  echo "==> $name"
  if "$@"; then
    echo "PASS $name"
  else
    echo "FAIL $name"
    failed+=("$name")
  fi
}

run web-build pnpm --filter @music-it/web build
run web-test pnpm test:web
run api-test bash -c 'cd apps/omr-service && .venv/bin/python -m pytest -q'

if [ "${#failed[@]}" -eq 0 ]; then
  echo "GATE PASS"
else
  echo "GATE FAIL: ${failed[*]}"
  exit 1
fi
