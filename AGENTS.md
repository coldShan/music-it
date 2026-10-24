# music-it 工程约定

## 结构
- `apps/web`：Vue 3 + Vite + TypeScript 前端。测试用 vitest + jsdom，测试文件与源码同目录，命名 `*.spec.ts`。
- `apps/omr-service`：FastAPI 后端（Python），测试在 `tests/`，用 pytest。
- `packages/shared-types`：前后端共享类型，包名 `@music-it/shared-types`。

## 命令
- 安装依赖：`pnpm install`
- 前端测试：`pnpm test:web`
- 前端类型检查 + 构建：`pnpm --filter @music-it/web build`
- 后端测试：`cd apps/omr-service && .venv/bin/python -m pytest`
- 门禁（全部检查）：`bash scripts/gate.sh`，退出码 0 才算通过。

## 规则
- 包管理只用 pnpm。不要新增依赖，除非任务卡明确允许。
- 先写会失败的测试，再写实现。新逻辑尽量写成纯函数放在 `apps/web/src/services/`，方便测试。
- 不要修改 `storage/`、`.gitignore`、`pnpm-lock.yaml`、`pnpm-workspace.yaml`，除非任务卡明确允许。
- 跟随周围代码的风格和注释密度；界面文案用中文。
- 只做任务要求的改动，不要顺手重构或格式化无关文件。

## 代理分工
本仓库较大的功能按"大脑 / 执行者 / 门禁"分工完成：
- **大脑**（Claude Code）：规划、写任务卡、审核、提交、合并。完整流程见 `.claude/skills/pi/SKILL.md`，用 `/pi` 触发。
- **执行者**（pi）：只按任务卡做，只改卡里"允许改动的文件"；不 git commit，不把任务派给其他代理。完成后运行门禁，用中文总结改动的文件、门禁结果和没解决的问题。发现卡里没写清的地方或已有代码的 bug，写进总结，不要自行扩大范围。
- **门禁**：`bash scripts/gate.sh`。

约定：
- 任务卡放在 `docs/tasks/<编号>-<英文短名>.md`，编号递增，模板是 `docs/tasks/_template.md`。
- 派活用 `bash scripts/pi-run.sh <卡>`；返工时第二个参数传审核意见，pi 会在同一会话里接着改。
- 每张卡在仓库外的 worktree `../music-it-worktrees/<卡名>` 里做，分支是 `pi/<卡名>`；运行日志在 `.agent-runs/`，不提交。
- 在 worktree 里联调真实曲库：`CATALOG_PROJECT_ROOT=<主仓库路径> pnpm dev`。
