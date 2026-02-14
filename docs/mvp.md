# Music It MVP

## 功能
- 上传 PNG/JPG/PDF（PDF 仅第一页）
- 后端调用 Audiveris 识别 MusicXML
- 解析 tempo、拍号、右手主旋律音符序列
- 新增双手播放事件（右手旋律 + 左手主伴奏声部）
- 按 MusicXML 语义输出断句字段（`gateBeat` / `phraseBreakAfter` / `articulation`）
- 前端展示音符表并自动弹奏（支持双手/只右手/只左手）
- 支持旋律/左手独立音色（钢琴、吉他、八音盒、小提琴、小号、萨克斯、笛子）
- 已识别曲目目录（持久化到项目目录，可直接播放、重命名、删除）

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
- `GET /api/v1/catalog`
- `GET /api/v1/catalog/{entry_id}`
- `PATCH /api/v1/catalog/{entry_id}`
- `DELETE /api/v1/catalog/{entry_id}`
- `POST /api/v1/catalog/reset?confirm=WIPE_CATALOG`

### notes 字段（识别响应）
- `startBeat`: 起始拍
- `durationBeat`: 记谱时值
- `gateBeat`: 实际播放时值（用于断句）
- `phraseBreakAfter`: 当前音后是否断句
- `articulation`: `normal | slur | staccato | tie`

### playbackEvents 字段（识别响应）
- `startBeat`: 事件起始拍
- `durationBeat`: 事件记谱时值（同起始拍多音取最大值）
- `gateBeat`: 事件实际播放时值（同起始拍多音取最大值）
- `pitches`: 同步播放音名数组（和弦）
- `midis`: 同步播放 MIDI 数组
- `hand`: `right | left`
- `staff`: 来源谱表
- `voice`: 来源声部
- `sourceMeasure`: 来源小节号

### 曲目音色字段
- `melodyInstrument`: 主旋律音色（默认 `piano`）
- `leftHandInstrument`: 左手音色（默认 `piano`）
- 支持值：`piano | guitar | musicBox | violin | trumpet | saxophone | flute`

### PATCH /api/v1/catalog/{entry_id}
- 支持部分更新，至少提供一个字段：
  - `title?: string`
  - `melodyInstrument?: InstrumentId`
  - `leftHandInstrument?: InstrumentId`

## 限制
- 仅支持印刷体五线谱；右手输出主旋律，左手仅取 `staff=2` 主伴奏声部。
- 音色样本首播需要网络加载，加载失败会自动回退钢琴。
- 暂不支持左手全声部混合、复杂装饰音、手写谱和实时摄像头。

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

## 已识别曲目目录存储
- 目录位于：`storage/catalog/`
  - `index.json`：目录索引
  - `images/`：已保存图片副本
  - `records/`：识别结果记录
- 同一图片按 SHA-256 去重，重复上传会复用已识别结果。
- 如需清空历史记录（含图片和记录文件），调用：
  ```bash
  curl -X POST "http://localhost:8000/api/v1/catalog/reset?confirm=WIPE_CATALOG"
  ```
