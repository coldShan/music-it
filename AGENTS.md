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
