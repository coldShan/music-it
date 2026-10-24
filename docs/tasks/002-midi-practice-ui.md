# 002-midi-practice-ui

## 角色
你是执行者。只按这张卡完成任务，不要把任务派给其他代理，不要 git commit。

## 目标
在试听室加上"电子琴练习"界面：连接 MIDI 设备、选择设备、设置小节范围和循环、开关按键回放，开始等待模式练习；卷帘图高亮当前要按的音、按对的音和按错的音；练习结束或停止后显示统计。

## 背景
- 核心逻辑已经在上一张卡里完成，直接使用，不要改它们的行为：
  - `apps/web/src/services/midiInput.ts`：`connectMidi`、`MidiConnection`、`MidiUnavailableError`（`message` 已是给用户看的中文提示）。
  - `apps/web/src/services/practice.ts`：`buildPracticeSteps`、`startPractice`、`handleNoteOn`、`summarizePractice`。
  - `apps/web/src/services/player.ts`：`preparePracticeInstruments`、`playCueNow`、`noteOnNow`、`noteOffNow`、`stopPracticeSounds`。
- 练习发声和 `playScore` 共用同一批音色播放器，`stopScore` 和 `stopPracticeSounds` 会互相停掉对方的声音，所以**练习和播放必须互斥**。
- 现有试听室在 `apps/web/src/App.vue`。左右手模式用现有的 `playbackMode`（`PlaybackModeGroup`），练习直接沿用它，不要另做一套选择。
- 卷帘图是 `apps/web/src/components/ScorePreview.vue`。

## 允许改动的文件
- 新建 `apps/web/src/components/PracticePanel.vue`、`apps/web/src/components/PracticePanel.spec.ts`
- 新建 `apps/web/src/components/ScorePreview.spec.ts`
- 修改 `apps/web/src/components/ScorePreview.vue`
- 修改 `apps/web/src/App.vue`、`apps/web/src/App.spec.ts`

## 规格

### 1. `PracticePanel.vue`：练习的全部状态和逻辑都在这个组件里
Props：
```ts
{
  events: PlaybackEvent[]
  tempo: number
  mode: PlaybackMode
  measureCount?: number | null
  melodyInstrument: InstrumentId
  leftHandInstrument: InstrumentId
}
```
Emits：
- `start`：开始练习时触发（App 用它停止播放）。
- `view`：载荷为 `{ beat: number; target: number[]; hits: number[]; wrong: number | null } | null`。练习中每次状态变化都发出；未在练习时发 `null`。
`defineExpose({ stop })`：App 在开始播放时调用它停止练习。

界面与行为（所有可交互元素带 `data-testid`）：
1. 未连接时显示"连接电子琴"按钮（`practice-connect`）。点击调用 `connectMidi()`。失败时在 `role="alert"` 区域显示错误的 `message`；不是 `MidiUnavailableError` 的错误显示"连接 MIDI 设备失败，请重试。"。
2. 连接成功后显示设备下拉框（`practice-device`）：第一项为"所有设备"（值 `'all'`，默认选中），其后是 `inputs()` 里的每个设备，显示 `name`，没有名字时显示"未命名设备"。用 `onInputsChange` 实时更新列表；当前选中的设备消失时退回 `'all'`。列表为空时显示提示"没有检测到 MIDI 设备，插上电子琴后会自动出现。"
3. 设置项：
   - 小节范围：两个数字输入（`practice-range-start`、`practice-range-end`），最小 1，最大为总小节数。总小节数取 `measureCount`；为空时取 `events` 里最大的 `sourceMeasure`。默认是全曲。起始大于结束时禁用开始按钮，并提示"起始小节不能大于结束小节"。
   - 循环练习复选框（`practice-loop`），默认关。
   - 回放按键声复选框（`practice-echo`），默认关，旁边说明"电子琴本身会出声时建议关闭"。
4. "开始练习"按钮（`practice-start`）：未连接、范围无效、或按当前模式和范围算出的需要弹的步数为 0 时禁用。点击后依次：
   - 发出 `start`；
   - `await preparePracticeInstruments([melodyInstrument, leftHandInstrument])`，返回的警告显示在面板里；
   - `buildPracticeSteps(events, mode, range)`，然后 `startPractice(steps, { loop })`；
   - 对输出的每个 `autoPlay` 调用 `playCueNow(cue, { tempo, melodyInstrument, leftHandInstrument })`；
   - `listen(选中的设备 id, 回调)` 开始监听。
5. 收到 MIDI 消息：
   - `noteon`：开启了回放按键声时，调用 `noteOnNow(midi, 音色, velocity)`，音色在 `mode === 'left'` 时用 `leftHandInstrument`，否则用 `melodyInstrument`。然后 `handleNoteOn(state, midi, Date.now())`，对输出的每个 `autoPlay` 调用 `playCueNow`。`feedback === 'wrong'` 时把 `wrong` 设为该 midi，400ms 后清回 `null`。`feedback === 'finished'` 时结束练习（同第 7 条，但保留统计）。
   - `noteoff`：开启了回放按键声时调用 `noteOffNow(midi)`。
6. 练习中显示进度（`practice-progress`），格式为"第 {当前需要弹的步序号} / {需要弹的总步数} 步 · 第 {小节} 小节 · 错音 {次数}"。只计 `required` 非空的步。循环时在末尾加"· 第 {passes + 1} 遍"。
7. "停止练习"按钮（`practice-stop`）以及 `stop()`：取消监听，调用 `stopPracticeSounds()`，发出 `view: null`。如果练习已经开始弹（`startedAt` 不为空），显示统计。
8. 统计（`practice-summary`），用 `summarizePractice`：用时（m:ss）、错音次数、完成遍数，以及"最常出错的小节"列表（为空时显示"没有错音"）。再次开始练习时隐藏统计。
9. 练习中 `events`、`mode`、小节范围或循环设置变化时自动停止练习（不显示统计）。
10. 组件卸载时取消监听、`close()` 连接、调用 `stopPracticeSounds()`。
11. `view` 载荷：`beat` 为当前步的 `beat`，`target` 为当前步的 `required`，`hits` 为当前 `hits`，`wrong` 见第 5 条。练习结束后发 `null`。

样式用 scoped CSS，跟随 `style.css` 里试听室的配色和间距（`var(--line)`、`var(--muted)`、`#627454`、圆角 6px），窄屏（≤ 620px）下设置项纵向排列。

### 2. `ScorePreview.vue`
新增可选 prop `practice?: { beat: number; target: number[]; hits: number[]; wrong: number | null } | null`。
- 有 `practice` 时，分页窗口和播放头都以 `practice.beat` 为准，忽略 `beat`。
- `startBeat` 与 `practice.beat` 相同（`Math.round(x * 1000)` 比较）的音符：midi 在 `hits` 里加 class `hit`，否则在 `target` 里加 class `target`。
- `wrong` 不为空时，在播放头位置、按该 midi 的纵坐标画一个短横标记（class `wrong-marker`）。纵坐标限制在当前音高范围内。
- 没有 `practice` 时，渲染和现在完全一致。
- 颜色：`target` 用深色描边加稍亮的填充，`hit` 用实心 `#627454`，`wrong-marker` 用 `#b5543c`。

### 3. `App.vue`
- 在 `practice-controls` 里"音色设置"按钮旁边加"电子琴练习"切换按钮（`practice-toggle`，带 `aria-expanded` 和 `aria-controls`），控制 `PracticePanel` 所在区域的显示。用 `v-show`，收起面板不会中断正在进行的练习。
- 传入 `resolvedPlaybackEvents`、`result.tempo`、`playbackMode`、`result.measureCount`、两个音色。
- 收到 `start` 时调用现有的 `onStop()`；`onPlay()` 开始时调用面板的 `stop()`。
- 用收到的 `view` 作为 `ScorePreview` 的 `practice` prop。
- 切换曲目、返回曲库、删除或清空曲库时，面板会因 `events` 变化或卸载而停止，不需要额外处理；但要确认这些场景下没有遗留的监听，并为此写测试。

## 验收
- `bash scripts/gate.sh` 退出码为 0。
- `PracticePanel.spec.ts`（mock `../services/midiInput` 和 `../services/player`，用可控的假连接手动触发 MIDI 回调）至少覆盖：
  - 连接失败时显示错误提示；
  - 设备列表渲染、默认"所有设备"、设备变化后列表更新、选中的设备消失后退回 `'all'`；
  - 开始时发出 `start`、预加载音色、以选中的设备 id 调用 `listen`、显示"第 1 / N 步"；
  - 按对前进；按错时错音数加 1，`view` 带上 `wrong`，400ms 后清除（用 fake timers）；
  - 右手练习时左手伴奏通过 `playCueNow` 发出，参数正确；
  - 回放按键声关闭时不调用 `noteOnNow`，开启时 `noteOnNow` / `noteOffNow` 参数正确，左手模式用左手音色；
  - 弹完显示统计并取消监听；循环时进度显示遍数且不结束；
  - 起始小节大于结束小节时开始按钮被禁用；
  - 练习中 `mode` 变化会停止练习（取消监听、`stopPracticeSounds` 被调用）；
  - 卸载时 `close()` 被调用。
- `ScorePreview.spec.ts` 覆盖：`target` / `hit` 的 class；`wrong-marker` 出现与消失；有 `practice` 时播放头位置跟随 `practice.beat`；没有 `practice` 时不出现这些 class。
- `App.spec.ts`：补全 player mock 里新增的函数并 mock `./services/midiInput`，现有测试全部继续通过；新增测试覆盖：
  - 开始练习会停止播放；
  - 播放会停止练习；
  - 切换到另一首曲目后不再保留旧曲目的监听。

## 不做
- 不改 `services/` 下的任何文件。如果发现核心逻辑有 bug，不要修，写在最后的总结里。
- 不做跟拍模式、忽略八度判定、屏幕键盘。
- 不改后端，不改 `shared-types`，不新增依赖。
