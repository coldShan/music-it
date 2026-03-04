# Music It

Music It 是一个乐谱识别与回放的本地开发项目。

- 前端：上传乐谱图片或 PDF，展示识别结果并回放音符
- 后端：调用 Audiveris 将乐谱转换为 MusicXML，再解析为可播放数据
- 存储：将已识别曲目保存在本地目录，支持再次播放、重命名、删除

## 环境要求

本项目建议先安装以下依赖：

- Node.js 20+
- `pnpm`
- Python 3.11+
- Java
- Audiveris

其中，**Audiveris 是必须安装的**。后端识别流程依赖 Audiveris 生成 MusicXML；如果没有安装，只能启动页面，但无法正常进行乐谱识别。

Audiveris 官网：[https://audiveris.com/](https://audiveris.com/)

安装完成后，请确保以下命令可用：

```bash
pnpm -v
python3 --version
java -version
audiveris --help
```

如果你的系统里不能直接执行 `audiveris`，可以通过环境变量手动指定可执行文件路径：

```bash
AUDIVERIS_CMD="/Applications/Audiveris.app/Contents/MacOS/Audiveris" pnpm dev
```

在 macOS 上，如果你把 Audiveris 安装在默认应用目录 `/Applications/Audiveris.app`，项目启动脚本会自动尝试使用：

```bash
/Applications/Audiveris.app/Contents/MacOS/Audiveris
```

## 运行说明

在项目根目录执行：

```bash
pnpm dev
```

这个命令会自动完成以下事情：

- 检查并选择可用端口
- 创建 `apps/omr-service/.venv`
- 安装后端 Python 依赖
- 安装前端工作区依赖
- 启动后端服务（默认 `8000`）
- 启动前端开发服务（默认 `5173`）

启动成功后，终端会打印实际地址，默认访问：

- 前端：[http://localhost:5173](http://localhost:5173)
- 后端：[http://localhost:8000](http://localhost:8000)

### 自定义端口

如果你想手动指定端口，可以这样启动：

```bash
WEB_PORT=5180 API_PORT=8001 pnpm dev
```

默认情况下，如果端口被占用，`scripts/dev.sh` 会自动顺延到下一个空闲端口。

## 使用说明

1. 启动项目：`pnpm dev`
2. 在浏览器打开前端页面
3. 上传乐谱文件（支持 `PNG`、`JPG`、`PDF`，PDF 仅处理第一页）
4. 等待后端调用 Audiveris 完成识别
5. 在页面中查看音符结果，并使用播放器试听

项目还会把识别过的内容保存到本地目录，便于后续复用：

- 目录位置：`storage/catalog/`
- 图片副本：`storage/catalog/images/`
- 识别结果：`storage/catalog/records/`

## 常用命令

启动完整开发环境：

```bash
pnpm dev
```

只启动前端：

```bash
pnpm dev:web
```

运行前端测试：

```bash
pnpm test:web
```

在后端已启动时，执行一个简单的接口联调示例（将路径替换为你自己的本地乐谱文件）：

```bash
./scripts/e2e-demo.sh /path/to/your-score.png
```

## 调试与排查

- 如果终端提示 `audiveris command not found`，说明 Audiveris 未安装，或未加入命令行路径。
- 如果已安装但无法直接调用，请使用 `AUDIVERIS_CMD` 指定可执行文件路径。
- 每次识别的运行日志默认保存在 `apps/omr-service/run-logs/`，可用于排查识别失败原因。

更多 MVP 细节可以参考 [docs/mvp.md](/Users/xingruifeng/develop/music-it/docs/mvp.md)。
