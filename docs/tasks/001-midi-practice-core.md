# 001-midi-practice-core

## 角色
你是执行者。只按这张卡完成任务，不要把任务派给其他代理，不要 git commit。

## 目标
为"连接 MIDI 电子琴、按识别出的乐谱做等待模式练习"实现**不含界面**的核心逻辑：MIDI 输入封装、练习状态机、练习用的即时发声接口。界面在下一张卡里做。

## 背景
- 乐谱数据是 `PlaybackEvent[]`（见 `packages/shared-types/src/index.ts`）。同一时刻的和弦已经归在一个 event 的 `midis` 里；连音线已合并；装饰音已丢弃。左右手由 `hand` 区分。
- 现有播放逻辑在 `apps/web/src/services/player.ts`：`PlaybackMode = 'both' | 'right' | 'left'`、`resolveHandInstrument`、soundfont 音色加载与 `toneSynth` 合成器。新代码要复用这些，不要另起一套音色加载。
- 等待模式：光标停在当前一拍，用户按对这一拍要求的所有音才前进。用户只练一只手时，另一只手的音由网页在用户按对后自动伴奏。

## 允许改动的文件
- 新建 `apps/web/src/services/midiInput.ts`、`apps/web/src/services/midiInput.spec.ts`
- 新建 `apps/web/src/services/practice.ts`、`apps/web/src/services/practice.spec.ts`
- 修改 `apps/web/src/services/player.ts`（只增加导出，不改变现有函数行为）
- 修改或新建 `apps/web/src/services/player.spec.ts`、`apps/web/src/services/player.practice.spec.ts`

## 规格

### 1. `midiInput.ts`
```ts
export type MidiNoteMessage = { type: 'noteon' | 'noteoff'; midi: number; velocity: number; channel: number }
export function parseMidiMessage(data: ArrayLike<number>): MidiNoteMessage | null

export type MidiInputInfo = { id: string; name: string }
export class MidiUnavailableError extends Error {
  reason: 'unsupported' | 'insecure' | 'denied'
}
export type MidiConnection = {
  inputs(): MidiInputInfo[]
  onInputsChange(callback: (inputs: MidiInputInfo[]) => void): () => void
  listen(inputId: string | 'all', callback: (message: MidiNoteMessage) => void): () => void
  close(): void
}
export async function connectMidi(env?: { navigator?: Navigator; isSecureContext?: boolean }): Promise<MidiConnection>
```
- `parseMidiMessage`：长度不足 3 返回 `null`。`status = data[0] & 0xf0`，`channel = (data[0] & 0x0f) + 1`。`0x90` 且力度 > 0 为 `noteon`；`0x90` 且力度 0、或 `0x80`，为 `noteoff`；其他状态字节返回 `null`。
- `connectMidi`：`env` 默认取 `globalThis.navigator` 和 `globalThis.isSecureContext`。先判断 `isSecureContext === false` → 抛 `reason: 'insecure'`；再判断没有 `requestMIDIAccess` → `'unsupported'`；`requestMIDIAccess()` 被拒绝 → `'denied'`。错误的 `message` 用中文，说明原因和解决办法（例如 insecure 时提示用 localhost 或 HTTPS 访问，unsupported 时提示用 Chrome / Edge）。
- `listen` 用 `addEventListener('midimessage', ...)`，回调只收到 `parseMidiMessage` 不为 `null` 的消息。`'all'` 表示监听所有输入，包括之后新插上的设备。返回的函数取消这次监听。
- `onInputsChange` 基于 MIDIAccess 的 `statechange` 事件。`close()` 移除本连接注册的所有监听。
- 测试中用手写的假 MIDIAccess（`inputs` 为 Map，输入和 access 都是 `EventTarget`）注入 `env.navigator`，不要依赖真实浏览器。

### 2. `practice.ts`（纯函数，不引用 Tone / soundfont / DOM）
```ts
export type PracticeStep = {
  index: number
  beat: number
  measure: number
  required: number[]              // 用户需要按的 midi，去重、升序
  accompaniment: PlaybackEvent[]  // 同一拍、由网页自动伴奏的事件
}
export type PracticeRange = { startMeasure: number; endMeasure: number } | null
export type AutoPlayCue = { delayBeats: number; events: PlaybackEvent[] }
export type PracticeFeedback = 'none' | 'hit' | 'wrong' | 'step-complete' | 'loop' | 'finished'
export type PracticeState = {
  steps: PracticeStep[]
  current: number                 // 当前等待的 step 下标；等于 steps.length 表示已结束
  hits: number[]                  // 当前 step 已按对的 midi
  loop: boolean
  passes: number                  // 完整弹完的遍数
  wrongCount: number
  wrongByMeasure: Record<number, number>
  startedAt: number | null        // 第一次 noteon 的时间（毫秒）
  finishedAt: number | null
}
export type PracticeOutput = { state: PracticeState; autoPlay: AutoPlayCue[]; feedback: PracticeFeedback }

export function buildPracticeSteps(events: PlaybackEvent[], mode: PlaybackMode, range?: PracticeRange): PracticeStep[]
export function startPractice(steps: PracticeStep[], options?: { loop?: boolean }): PracticeOutput
export function handleNoteOn(state: PracticeState, midi: number, now: number): PracticeOutput
export function summarizePractice(state: PracticeState, now: number): {
  passes: number; wrongCount: number; elapsedMs: number; worstMeasures: { measure: number; count: number }[]
}
```
规则：
- `buildPracticeSteps`：先按 `range` 过滤 `sourceMeasure`（闭区间，`null`/省略表示不过滤），再按 `startBeat` 分组（用 `Math.round(beat * 1000)` 作分组键），按拍子升序排列。`mode === 'both'` 或 `event.hand === mode` 的事件，其 `midis` 进入 `required`；其余事件进入 `accompaniment`。`measure` 取该组里最小的 `sourceMeasure`。`required` 为空的 step（只有伴奏）也保留，称为"自动步"。
- 状态更新一律返回新对象，不修改传入的 state。
- `startPractice`：从第一个 step 开始。开头连续的自动步直接作为 `autoPlay` 输出（`delayBeats = 该步 beat - 第一步 beat`），`current` 停在第一个 `required` 非空的 step。全部都是自动步时直接视为结束（`feedback: 'finished'`）。
- `handleNoteOn`：
  - 已结束（`current >= steps.length`）→ 原样返回，`feedback: 'none'`。
  - `startedAt` 为 `null` 时记为 `now`。
  - midi 在当前 step 的 `required` 里且还没按过 → 加进 `hits`，`feedback: 'hit'`；已经按过 → `feedback: 'none'`。
  - midi 不在 `required` 里 → `wrongCount + 1`，`wrongByMeasure[当前 step.measure] + 1`，`feedback: 'wrong'`，不前进。
  - 和弦不要求同时按住：本步里按过的音累计，`required` 全部出现在 `hits` 里即完成本步。
  - 完成本步时：`autoPlay` 先放 `{ delayBeats: 0, events: 本步 accompaniment }`（为空则不放），再依次放之后紧跟的自动步（`delayBeats = 自动步 beat - 本步 beat`），直到下一个 `required` 非空的 step；`current` 移到那里，`hits` 清空，`feedback: 'step-complete'`。
  - 完成最后一个需要用户弹的 step 时：`passes + 1`。如果 `loop` 为真，回到开头，按 `startPractice` 的方式再输出开头的自动步，但每个 `delayBeats` 额外加 1，`feedback: 'loop'`；否则 `current = steps.length`、`finishedAt = now`，`feedback: 'finished'`。
- `summarizePractice`：`elapsedMs` = （`finishedAt ?? now`）减 `startedAt`，没开始时为 0；`worstMeasures` 按错误次数降序，次数相同按小节号升序，最多 3 项，不含 0 次的小节。

### 3. `player.ts` 新增导出（不改变 `playScore` / `seekScore` / `stopScore` 的现有行为）
```ts
export function midiToPitch(midi: number): string                     // 60 → 'C4'，61 → 'C#4'，21 → 'A0'
export async function preparePracticeInstruments(ids: InstrumentId[]): Promise<string[]>  // 调用 Tone.start() 并预加载音色，返回回退警告
export function playCueNow(cue: AutoPlayCue, options: { tempo: number; melodyInstrument: InstrumentId; leftHandInstrument: InstrumentId }): void
export function noteOnNow(midi: number, instrumentId: InstrumentId, velocity: number): void
export function noteOffNow(midi: number): void
export function stopPracticeSounds(): void
```
- 音色加载复用现有的 `loadInstrumentWithFallback` 和缓存；`toneSynth` 复用同一个 `PolySynth` 的创建参数。
- `playCueNow`：立即调度，`delaySeconds = cue.delayBeats * 60 / tempo`，每个事件的时值用 `gateBeat * 60 / tempo`，用 `resolveHandInstrument` 选音色，左手增益与 `playScore` 一致。调用前没有预加载的音色就跳过，不抛错。
- `noteOnNow` / `noteOffNow`：给"网页回放按键声"用。按住期间持续发声，`noteOffNow` 时停止；力度映射为增益 `velocity / 127`。
- `stopPracticeSounds`：停止所有由上述函数发出的声音。

## 验收
- `bash scripts/gate.sh` 退出码为 0。
- `midiInput.spec.ts` 至少覆盖：noteon、力度 0 的 noteon 视为 noteoff、0x80 noteoff、通道号解析、非音符消息和过短消息返回 null；insecure / unsupported / denied 三种错误；`listen('all')` 能收到之后新插上设备的消息；取消监听后不再回调；`close()` 后不再回调。
- `practice.spec.ts` 至少覆盖：按拍分组和 `required` / `accompaniment` 的划分（both / right / left 三种模式）；小节范围过滤；单音按对前进；错音计数且不前进；同一拍内重复按同一个音不重复计；和弦以任意顺序按齐才完成；完成后输出本步伴奏和后续自动步的 `delayBeats`；开头的自动步由 `startPractice` 输出；非循环结束时的 `finished` 和 `finishedAt`；循环时回到开头、`passes` 递增、开头自动步的 `delayBeats` 加 1；传入的 state 不被修改；`summarizePractice` 的排序和截断。
- `player.ts` 新增函数的测试：`midiToPitch` 的边界值；`playCueNow` 用 mock 验证音色选择、延迟和时值换算。参考 `player.lifecycle.spec.ts` 里 mock Tone 和 soundfont 的方式。

## 不做
- 不改任何 `.vue` 组件和 `App.vue`，不做界面。
- 不做跟拍模式（按节拍计时判定）和忽略八度判定。
- 不改后端，不改 `shared-types`，不新增依赖。
