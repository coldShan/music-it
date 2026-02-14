# Music It MVP

## 功能
- 上传 PNG/JPG/PDF（PDF 仅第一页）
- 后端调用 Audiveris 识别 MusicXML
- 解析 tempo、拍号、单旋律音符序列
- 前端展示音符表并自动弹奏

## 本地运行
1. 安装 Node 20+, pnpm, Python 3.11+, Java。
2. 安装 Audiveris，并确保 `audiveris` 可在命令行执行。
3. 在项目根目录执行：
   ```bash
   pnpm dev
   ```
4. 打开 `http://localhost:5173`。

### 端口冲突处理
- `scripts/dev.sh` 默认前端 `5173`、后端 `8000`，端口占用时会自动顺延到空闲端口并打印实际 URL。
- 也可手动指定端口：
  ```bash
  WEB_PORT=5180 API_PORT=8001 pnpm dev
  ```

### Audiveris 本地安装
- 若已安装到 `/Applications/Audiveris.app`，`scripts/dev.sh` 会自动使用：
  `/Applications/Audiveris.app/Contents/MacOS/Audiveris`
- 或者你也可以手动指定：
  ```bash
  AUDIVERIS_CMD="/Applications/Audiveris.app/Contents/MacOS/Audiveris" pnpm dev
  ```

## 验收脚本
1. 启动后端服务（`pnpm dev` 已包含）。
2. 执行：
   ```bash
   ./scripts/e2e-demo.sh ./tests/samples/hometown-taste.png
   ```
3. 在前端页面上传同一文件，确认自动弹奏与音符表展示。

## API
- `GET /api/v1/health`
- `POST /api/v1/recognize` (multipart/form-data, field: `file`)

## 限制
- 仅支持印刷体五线谱单旋律。
- 暂不支持双手钢琴谱、装饰音、手写谱和实时摄像头。

## 识别日志与复盘
- 每次识别都会在后端生成运行日志目录：`apps/omr-service/run-logs/<run-id>/`
- 关键文件包括：
  - `run-meta.json`：输入与启动信息
  - `preprocessed.png`：预处理后的图像
  - `audiveris-command.txt` / `audiveris-stdout.log` / `audiveris-stderr.log`
  - `audiveris-files.txt`：识别过程产生的文件清单
  - `result-summary.json`：成功或失败摘要
- 可通过环境变量调整日志目录：
  ```bash
  OMR_RUN_LOG_DIR=/your/path pnpm dev
  ```
