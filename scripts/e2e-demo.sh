#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <score-file-path>"
  exit 1
fi

FILE_PATH="$1"
API_BASE="${API_BASE:-http://localhost:8000}"

echo "== health =="
curl -sS "$API_BASE/api/v1/health" | sed 's/.*/  &/'

echo "== recognize =="
curl -sS -X POST "$API_BASE/api/v1/recognize" \
  -F "file=@${FILE_PATH}" | sed 's/.*/  &/'

echo "\nDone. Open http://localhost:5173 and upload the same file for playback UI."
