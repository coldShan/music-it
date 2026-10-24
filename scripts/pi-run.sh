#!/usr/bin/env bash
# 把一张任务卡派给 pi 执行。
# 用法：
#   scripts/pi-run.sh docs/tasks/001-xxx.md              首次派活（新建 worktree 和会话）
#   scripts/pi-run.sh docs/tasks/001-xxx.md "修改意见"    在同一会话里返工
# 环境变量：PI_MODEL 覆盖默认模型；PI_BASE 指定新 worktree 的起点（默认 HEAD）。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CARD="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
FEEDBACK="${2:-}"
NAME="$(basename "$CARD" .md)"
WORKTREE="$(dirname "$ROOT_DIR")/$(basename "$ROOT_DIR")-worktrees/$NAME"
BRANCH="pi/$NAME"
MODEL="${PI_MODEL:-opencode-go/deepseek-v4.1-flash:high}"
BASE="${PI_BASE:-HEAD}"
LOG_DIR="$ROOT_DIR/.agent-runs"
LOG="$LOG_DIR/$NAME-$(date +%Y%m%d-%H%M%S).log"

[ -f "$CARD" ] || { echo "Task card not found: $CARD" >&2; exit 1; }
mkdir -p "$LOG_DIR"

if [ ! -d "$WORKTREE" ]; then
  git -C "$ROOT_DIR" worktree add -b "$BRANCH" "$WORKTREE" "$BASE"
  (cd "$WORKTREE" && bash scripts/worktree-setup.sh)
fi

ROLE="你是执行者：只负责按任务卡把活干完，不要把任务派给其他代理，不要 git commit。完成后运行 bash scripts/gate.sh，最后用中文输出总结：改动的文件、门禁结果、没解决或不确定的问题。"

if [ -z "$FEEDBACK" ]; then
  PROMPT="$ROLE 任务卡内容见附带的文件。"
else
  PROMPT="$ROLE 审核意见如下，请据此修改：$FEEDBACK"
fi

cd "$WORKTREE"
echo "worktree: $WORKTREE  branch: $BRANCH  model: $MODEL  log: $LOG"
set +e
if [ -z "$FEEDBACK" ]; then
  pi -p --model "$MODEL" --no-skills --session-id "$NAME" "@$CARD" "$PROMPT" 2>&1 | tee "$LOG"
else
  pi -p --model "$MODEL" --no-skills --session-id "$NAME" "$PROMPT" 2>&1 | tee "$LOG"
fi
status="${PIPESTATUS[0]}"
set -e
echo "pi exit: $status"
exit "$status"
