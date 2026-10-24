<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { InstrumentId, PlaybackEvent } from '@music-it/shared-types'
import {
  connectMidi,
  MidiUnavailableError,
  type MidiConnection,
  type MidiInputInfo,
  type MidiNoteMessage,
} from '../services/midiInput'
import {
  buildPracticeSteps,
  handleNoteOn,
  startPractice,
  summarizePractice,
  type PracticeState,
} from '../services/practice'
import {
  noteOffNow,
  noteOnNow,
  playCueNow,
  preparePracticeInstruments,
  stopPracticeSounds,
  type PlaybackMode,
} from '../services/player'

type PracticeView = { beat: number; target: number[]; hits: number[]; wrong: number | null }
type PracticeSummary = ReturnType<typeof summarizePractice>

const props = defineProps<{
  events: PlaybackEvent[]
  tempo: number
  mode: PlaybackMode
  measureCount?: number | null
  melodyInstrument: InstrumentId
  leftHandInstrument: InstrumentId
}>()

const emit = defineEmits<{ start: []; view: [value: PracticeView | null] }>()

const connection = ref<MidiConnection | null>(null)
const inputs = ref<MidiInputInfo[]>([])
const selectedDevice = ref<string>('all')
const connecting = ref(false)
const connectError = ref('')
const warnings = ref<string[]>([])
const preparing = ref(false)
const running = ref(false)
const practiceState = ref<PracticeState | null>(null)
const summary = ref<PracticeSummary | null>(null)
const wrong = ref<number | null>(null)
const loop = ref(false)
const echo = ref(false)

let detachInputsChange: (() => void) | null = null
let detachListen: (() => void) | null = null
let wrongTimer: ReturnType<typeof setTimeout> | undefined
let startRequest = 0

const totalMeasures = computed(() => {
  if (props.measureCount != null && props.measureCount > 0) return props.measureCount
  const fromEvents = props.events.reduce((end, event) => Math.max(end, event.sourceMeasure), 0)
  return Math.max(1, fromEvents)
})

const rangeStart = ref(1)
const rangeEnd = ref(totalMeasures.value)
const rangeInvalid = computed(() => rangeStart.value > rangeEnd.value)

const range = computed(() => ({
  startMeasure: rangeStart.value,
  endMeasure: rangeEnd.value,
}))
const previewSteps = computed(() => buildPracticeSteps(props.events, props.mode, range.value))
const requiredStepCount = computed(
  () => previewSteps.value.filter((step) => step.required.length > 0).length,
)

const canStart = computed(
  () =>
    !!connection.value &&
    !running.value &&
    !rangeInvalid.value &&
    requiredStepCount.value > 0,
)

const requiredOrdinal = computed(() => {
  const state = practiceState.value
  if (!state) return 0
  return state.steps
    .slice(0, state.current + 1)
    .filter((step) => step.required.length > 0).length
})
const requiredTotal = computed(() => {
  const state = practiceState.value
  if (!state) return 0
  return state.steps.filter((step) => step.required.length > 0).length
})
const currentMeasure = computed(() => {
  const state = practiceState.value
  if (!state || !state.steps.length) return 1
  const step = state.steps[Math.min(state.current, state.steps.length - 1)]
  return step?.measure ?? 1
})
const progressText = computed(() => {
  const state = practiceState.value
  if (!state) return ''
  const loopSuffix = state.loop ? ` · 第 ${state.passes + 1} 遍` : ''
  return `第 ${requiredOrdinal.value} / ${requiredTotal.value} 步 · 第 ${currentMeasure.value} 小节 · 错音 ${state.wrongCount} 次${loopSuffix}`
})

function formatElapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

function emitView(): void {
  const state = practiceState.value
  if (!running.value || !state) {
    emit('view', null)
    return
  }
  const step = state.steps[state.current]
  if (!step) {
    emit('view', null)
    return
  }
  emit('view', { beat: step.beat, target: step.required, hits: state.hits, wrong: wrong.value })
}

function clearWrong(): void {
  if (wrongTimer !== undefined) {
    clearTimeout(wrongTimer)
    wrongTimer = undefined
  }
  wrong.value = null
}

function stopListening(): void {
  detachListen?.()
  detachListen = null
}

function cancelPendingStart(): void {
  startRequest += 1
  preparing.value = false
}

function finishPractice(): void {
  const state = practiceState.value
  if (!state) return
  clearWrong()
  running.value = false
  summary.value = state.startedAt !== null ? summarizePractice(state, Date.now()) : null
  practiceState.value = null
  emit('view', null)
}

function stopPractice(options: { showSummary?: boolean } = {}): void {
  cancelPendingStart()
  const state = practiceState.value
  if (!running.value && !state) {
    stopListening()
    emit('view', null)
    return
  }
  const shouldSummarize = (options.showSummary ?? true) && !!state && state.startedAt !== null
  stopListening()
  stopPracticeSounds()
  clearWrong()
  running.value = false
  summary.value = shouldSummarize && state ? summarizePractice(state, Date.now()) : null
  practiceState.value = null
  emit('view', null)
}

function resetRange(): void {
  rangeStart.value = 1
  rangeEnd.value = totalMeasures.value
}

async function onConnect(): Promise<void> {
  if (connecting.value || connection.value) return
  connecting.value = true
  connectError.value = ''
  try {
    const connected = await connectMidi()
    connection.value = connected
    inputs.value = connected.inputs()
    selectedDevice.value = 'all'
    detachInputsChange = connected.onInputsChange((next) => {
      inputs.value = next
      if (
        selectedDevice.value !== 'all' &&
        !next.some((input) => input.id === selectedDevice.value)
      ) {
        selectedDevice.value = 'all'
      }
    })
  } catch (error) {
    connectError.value =
      error instanceof MidiUnavailableError
        ? error.message
        : '连接 MIDI 设备失败，请重试。'
  } finally {
    connecting.value = false
  }
}

function setWrong(midi: number): void {
  clearWrong()
  wrong.value = midi
  wrongTimer = setTimeout(() => {
    wrongTimer = undefined
    wrong.value = null
    emitView()
  }, 400)
}

function onMidiMessage(message: MidiNoteMessage): void {
  if (message.type === 'noteoff') {
    if (echo.value) noteOffNow(message.midi)
    return
  }

  if (!running.value || !practiceState.value) return

  if (echo.value) {
    const instrument =
      props.mode === 'left' ? props.leftHandInstrument : props.melodyInstrument
    noteOnNow(message.midi, instrument, message.velocity)
  }

  const output = handleNoteOn(practiceState.value, message.midi, Date.now())
  practiceState.value = output.state

  for (const cue of output.autoPlay) {
    playCueNow(cue, {
      tempo: props.tempo,
      melodyInstrument: props.melodyInstrument,
      leftHandInstrument: props.leftHandInstrument,
    })
  }

  if (output.feedback === 'wrong') setWrong(message.midi)

  if (output.feedback === 'finished') {
    finishPractice()
    return
  }

  emitView()
}

async function onStart(): Promise<void> {
  if (!canStart.value || preparing.value) return
  const request = ++startRequest
  summary.value = null
  warnings.value = []
  connectError.value = ''
  emit('start')
  preparing.value = true
  try {
    const loadedWarnings = await preparePracticeInstruments([
      props.melodyInstrument,
      props.leftHandInstrument,
    ])
    if (request !== startRequest) return
    warnings.value = loadedWarnings
    const steps = buildPracticeSteps(props.events, props.mode, range.value)
    const output = startPractice(steps, { loop: loop.value })
    practiceState.value = output.state
    running.value = true
    for (const cue of output.autoPlay) {
      playCueNow(cue, {
        tempo: props.tempo,
        melodyInstrument: props.melodyInstrument,
        leftHandInstrument: props.leftHandInstrument,
      })
    }
    stopListening()
    detachListen =
      connection.value?.listen(selectedDevice.value, onMidiMessage) ?? null
    if (output.feedback === 'finished') {
      finishPractice()
      return
    }
    emitView()
  } catch (error) {
    if (request !== startRequest) return
    running.value = false
    practiceState.value = null
    connectError.value =
      error instanceof Error ? error.message : '练习准备失败，请重试。'
  } finally {
    if (request === startRequest) preparing.value = false
  }
}

watch(
  () => props.events,
  () => {
    cancelPendingStart()
    if (running.value) stopPractice({ showSummary: false })
    summary.value = null
    resetRange()
  },
)
watch(totalMeasures, (total) => {
  cancelPendingStart()
  rangeStart.value = Math.min(Math.max(1, rangeStart.value), total)
  rangeEnd.value = Math.min(Math.max(rangeEnd.value, rangeStart.value), total)
})
watch([() => props.mode, rangeStart, rangeEnd, loop], () => {
  cancelPendingStart()
  if (running.value) stopPractice({ showSummary: false })
})

onUnmounted(() => {
  cancelPendingStart()
  stopListening()
  detachInputsChange?.()
  detachInputsChange = null
  clearWrong()
  stopPracticeSounds()
  connection.value?.close()
  connection.value = null
})

defineExpose({ stop: stopPractice })
</script>

<template>
  <section class="practice-panel" aria-label="电子琴练习">
    <div class="panel-heading">
      <div>
        <p class="eyebrow">PLAY ALONG</p>
        <h3>电子琴练习</h3>
      </div>
      <span class="connection-state" :class="{ online: connection }">
        {{ connection ? '已连接' : '未连接' }}
      </span>
    </div>

    <button
      v-if="!connection"
      type="button"
      class="practice-button"
      data-testid="practice-connect"
      :disabled="connecting"
      @click="onConnect"
    >
      {{ connecting ? '正在连接…' : '连接电子琴' }}
    </button>
    <p v-if="connectError" class="panel-error" role="alert">{{ connectError }}</p>

    <template v-if="connection">
      <div class="device-row">
        <label class="device-field">
          <span>MIDI 设备</span>
          <select v-model="selectedDevice" data-testid="practice-device">
            <option value="all">所有设备</option>
            <option v-for="input in inputs" :key="input.id" :value="input.id">
              {{ input.name || '未命名设备' }}
            </option>
          </select>
        </label>
        <p v-if="!inputs.length" class="field-hint">
          没有检测到 MIDI 设备，插上电子琴后会自动出现。
        </p>
      </div>

      <div class="practice-settings">
        <fieldset class="range-field">
          <legend>小节范围</legend>
          <input
            v-model.number="rangeStart"
            type="number"
            min="1"
            :max="totalMeasures"
            aria-label="起始小节"
            data-testid="practice-range-start"
          >
          <span aria-hidden="true">—</span>
          <input
            v-model.number="rangeEnd"
            type="number"
            min="1"
            :max="totalMeasures"
            aria-label="结束小节"
            data-testid="practice-range-end"
          >
          <span class="range-total">共 {{ totalMeasures }} 小节</span>
        </fieldset>
        <label class="check-field">
          <input v-model="loop" type="checkbox" data-testid="practice-loop">
          循环练习
        </label>
        <label class="check-field">
          <input v-model="echo" type="checkbox" data-testid="practice-echo">
          回放按键声
        </label>
        <p class="field-hint echo-hint">电子琴本身会出声时建议关闭</p>
      </div>
    </template>

    <p v-if="rangeInvalid" class="panel-error" role="alert">起始小节不能大于结束小节</p>
    <ul v-if="warnings.length" class="panel-warning" role="status">
      <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
    </ul>

    <div class="practice-actions">
      <button
        v-if="!running"
        type="button"
        class="practice-button primary"
        data-testid="practice-start"
        :disabled="!canStart || preparing"
        @click="onStart"
      >
        {{ preparing ? '正在准备…' : '开始练习' }}
      </button>
      <button
        v-else
        type="button"
        class="practice-button"
        data-testid="practice-stop"
        @click="stopPractice()"
      >
        停止练习
      </button>
    </div>

    <p v-if="running && practiceState" class="practice-progress" data-testid="practice-progress">
      {{ progressText }}
    </p>

    <section v-if="summary" class="practice-summary" data-testid="practice-summary">
      <h3>本轮练习</h3>
      <p class="summary-line">
        用时 {{ formatElapsed(summary.elapsedMs) }} · 错音 {{ summary.wrongCount }} 次 · 完成
        {{ summary.passes }} 遍
      </p>
      <div class="summary-worst">
        <span>最常出错的小节</span>
        <ul v-if="summary.worstMeasures.length">
          <li v-for="entry in summary.worstMeasures" :key="entry.measure">
            第 {{ entry.measure }} 小节 · {{ entry.count }} 次
          </li>
        </ul>
        <p v-else>没有错音</p>
      </div>
    </section>
  </section>
</template>

<style scoped>
.practice-panel {
  display: grid;
  gap: 18px;
  margin-top: 24px;
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfaf4;
}

.panel-heading {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.panel-heading h3 {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 500;
}

.connection-state {
  font-size: 10px;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 4px 8px;
}

.connection-state.online {
  color: #627454;
  border-color: #cbd4bf;
  background: #eef1e6;
}

.practice-button {
  justify-self: start;
  padding: 10px 16px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: transparent;
  color: #627454;
  font-size: 12px;
}

.practice-button.primary {
  background: #627454;
  border-color: #627454;
  color: #fffefa;
}

.practice-button.primary:hover:not(:disabled) {
  background: #4f5f43;
}

.device-row {
  display: grid;
  gap: 8px;
}

.device-field,
.range-field {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--muted);
}

.device-field select {
  min-width: 180px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fffefa;
  color: #252923;
  font-size: 12px;
}

.practice-settings {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, auto));
  align-items: center;
  gap: 12px 24px;
}

.range-field {
  grid-column: 1 / -1;
  margin: 0;
  padding: 0;
  border: 0;
}

.range-field legend {
  padding: 0;
  margin-right: 10px;
}

.range-field input {
  width: 64px;
  padding: 7px 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fffefa;
  color: #252923;
  font-size: 12px;
}

.range-total {
  font-size: 11px;
  color: var(--muted);
}

.check-field {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: #5e6853;
}

.check-field input {
  accent-color: #627454;
}

.field-hint {
  font-size: 11px;
  line-height: 1.6;
  color: var(--muted);
}

.echo-hint {
  grid-column: 1 / -1;
  margin-top: -6px;
}

.panel-error {
  font-size: 12px;
  color: #924b3b;
}

.panel-warning {
  margin: 0;
  padding-left: 18px;
  color: #926b3f;
  font-size: 12px;
  line-height: 1.7;
}

.practice-actions {
  display: flex;
  gap: 12px;
}

.practice-progress {
  font-size: 12px;
  color: #4f5f43;
  background: #eef1e6;
  border: 1px solid #e3e8d9;
  border-radius: 6px;
  padding: 10px 14px;
  font-variant-numeric: tabular-nums;
}

.practice-summary {
  display: grid;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.practice-summary h3 {
  font-size: 13px;
  font-weight: 600;
  color: #4f5f43;
}

.summary-line {
  font-size: 13px;
  color: #252923;
  font-variant-numeric: tabular-nums;
}

.summary-worst {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  font-size: 11px;
  color: var(--muted);
}

.summary-worst ul {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: #5e6853;
}

.summary-worst p {
  color: #5e6853;
}

@media (max-width: 620px) {
  .practice-panel {
    padding: 16px;
  }

  .practice-settings {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .range-field {
    flex-wrap: wrap;
  }

  .echo-hint {
    margin-top: 0;
  }

  .device-field {
    align-items: stretch;
    flex-direction: column;
  }

  .device-field select {
    min-width: 0;
    width: 100%;
  }
}
</style>
