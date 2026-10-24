---
name: pi
description: Use when the user in music-it asks to have pi implement something ("让 pi 做", "派给 pi", "写任务卡", "/pi"), or wants a sizeable feature built through the task-card / pi / gate / review workflow instead of Claude writing the code directly.
---

# 派活给 pi

## 原则
Claude 是大脑：规划、写任务卡、审核、提交。pi 是执行者：在独立 worktree 里按卡写代码，跑门禁。`bash scripts/gate.sh` 是机械检查。省 token 靠两点：代码不经 Claude 手写，审核时只读有风险的部分。

## 什么时候不用
- 改动预计少于约 100 行，或只改一两个文件：Claude 直接做更便宜。
- 需求还没想清楚：先和用户确认，再写卡。

## 流程
1. **确认需求**：有不确定的先用 AskUserQuestion 问。
2. **写卡**：复制 `docs/tasks/_template.md` 为 `docs/tasks/<下一个编号>-<英文短名>.md`。
   - 写到接口签名、行为规则、验收用例和"不做"就够了，不要写成伪代码。
   - 卡里要写清：允许改动的文件、必须有的测试。
   - 任务大时拆成多张卡，每张能独立通过门禁，按依赖顺序派。
3. **提交卡**：把卡提交到当前分支，方便追溯。
4. **派活**：用 Bash 的 `run_in_background` 运行，等完成通知，不要轮询。
   ```bash
   bash scripts/pi-run.sh docs/tasks/<卡>.md
   ```
   要基于上一张卡的分支开工，加 `PI_BASE=pi/<上一张卡>`。
5. **审核**（在 worktree `../music-it-worktrees/<卡名>` 里做）：
   - 读 pi 的总结（日志在 `.agent-runs/`），自己重跑 `bash scripts/gate.sh`，不要信 pi 报的结果。
   - `git status --short` 和 `git diff --stat`：检查是否改了卡外的文件。
   - 只读高风险的部分：异步和竞态、计时与音频、资源清理（监听、定时器、卸载）、和现有行为的交界。测试文件只抽查断言是否真在测规格。
6. **返工**：意见写成编号清单，每条说清现象、位置和期望行为，然后运行：
   ```bash
   bash scripts/pi-run.sh docs/tasks/<卡>.md "<意见>"
   ```
   pi 会在同一会话里改。改完回到第 5 步。
7. **提交**：审核通过后，在 worktree 里 `git add -A && git commit`，提交信息用中文，格式 `feat: ...`。
8. **交给用户**：说明分支 `pi/<卡名>`、门禁结果、已知限制，以及怎么手动验证（worktree 里联调真实曲库用 `CATALOG_PROJECT_ROOT=<主仓库路径> pnpm dev`）。合并由用户决定。
9. **合并与清理**（用户同意后才做）：
   - 在主仓库运行 `git merge --no-ff pi/<卡名>`，合并后再跑一次门禁；
   - 停掉 worktree 里的进程：`pkill -INT -f music-it-worktrees/<卡名>`；
   - 删除 worktree 和分支：`git worktree remove` 加 `git branch -d`。

## 常见错误
| 错误 | 正确做法 |
|---|---|
| 门禁绿了就直接提交 | 门禁测不出时序和声音问题，第 5 步的高风险项必须看 |
| 审核时整份读 diff | 先看 `--stat`，再按风险挑着读 |
| 在长对话里派活 | 新开会话做派活和审核，上下文小，每轮都更便宜 |
| 自己动手改 pi 的代码 | 小问题也走返工；只有一两行、且返工更贵时才自己改，并在交付时说明 |
| 没经同意就合并或推送 | 合并、推送、删分支都要用户点头 |
