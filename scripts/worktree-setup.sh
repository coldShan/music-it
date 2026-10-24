#!/usr/bin/env bash
# 在新建的 worktree 里补齐运行和测试所需的依赖与本地环境。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OMR_DIR="$ROOT_DIR/apps/omr-service"
cd "$ROOT_DIR"

pnpm install --frozen-lockfile

if [ ! -d "$OMR_DIR/.venv" ]; then
  python3 -m venv "$OMR_DIR/.venv"
fi
"$OMR_DIR/.venv/bin/pip" install -q -r "$OMR_DIR/requirements.txt"
