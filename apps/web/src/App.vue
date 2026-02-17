<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import type {
  CatalogEntryDetail,
  CatalogEntrySummary,
  InstrumentId,
  PlaybackEvent,
  RecognizeApiResponse,
  RecognizeResponse,
} from '@music-it/shared-types'

import { instrumentLabelMap, instrumentOptions } from './constants/instruments'
import CatalogList from './components/CatalogList.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import InstrumentListbox from './components/InstrumentListbox.vue'
import PlaybackModeGroup from './components/PlaybackModeGroup.vue'
import RecognizeDialog from './components/RecognizeDialog.vue'
import ResultTable from './components/ResultTable.vue'
import {
  deleteCatalogEntry,
  getCatalogEntry,
  listCatalogEntries,
  recognizeScore,
  resetCatalog,
  updateCatalogEntry,
} from './services/api'
import { filterPlaybackEvents, playScore, stopScore, type PlaybackMode } from './services/player'

const selectedFile = ref<File | null>(null)
const recognizeDialogOpen = ref(false)
const confirmResetOpen = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const result = ref<RecognizeResponse | null>(null)
const autoPlayMessage = ref('')
const recognizeStatus = ref('')

const catalogEntries = ref<CatalogEntrySummary[]>([])
const catalogLoading = ref(false)
const activeCatalogId = ref<string | null>(null)
const resetLoading = ref(false)
const instrumentSaving = ref(false)
const playbackMode = ref<PlaybackMode>('both')
const melodyInstrument = ref<InstrumentId>('piano')
const leftHandInstrument = ref<InstrumentId>('piano')

const editingCatalogId = ref<string | null>(null)
const editingCatalogTitle = ref('')

const sidebarDefaultOpen =
  typeof window === 'undefined' || typeof window.matchMedia !== 'function'
    ? true
    : window.matchMedia('(min-width: 769px)').matches

const activeCatalogEntry = computed(() => {
  if (!activeCatalogId.value) {
    return null
  }
  return catalogEntries.value.find((entry) => entry.id === activeCatalogId.value) ?? null
})

const activeTitle = computed(() => {
  return activeCatalogEntry.value?.title ?? (result.value ? '当前识别结果' : '尚未加载曲目')
})

function fallbackPlaybackEventsFromNotes(scoreNotes: RecognizeResponse['notes']): PlaybackEvent[] {
  return scoreNotes.map((note) => ({
    startBeat: note.startBeat,
    durationBeat: note.durationBeat,
    gateBeat: note.gateBeat,
    pitches: [note.pitch],
    midis: [note.midi],
    hand: 'right',
    staff: '1',
    voice: '1',
    sourceMeasure: note.sourceMeasure,
  }))
}

const resolvedPlaybackEvents = computed(() => {
  if (!result.value) {
    return [] as PlaybackEvent[]
  }
  if (result.value.playbackEvents?.length) {
    return result.value.playbackEvents
  }
  return fallbackPlaybackEventsFromNotes(result.value.notes)
})

const canPlay = computed(() => !!resolvedPlaybackEvents.value.length)
const melodyInstrumentLabel = computed(() => instrumentLabelMap[melodyInstrument.value])
const leftHandInstrumentLabel = computed(() => instrumentLabelMap[leftHandInstrument.value])

function toRecognizeResponse(response: RecognizeApiResponse): RecognizeResponse {
  return {
    tempo: response.tempo,
    timeSignature: response.timeSignature,
    notes: response.notes,
    playbackEvents: response.playbackEvents ?? [],
    meta: response.meta,
  }
}

function deriveTitleFromFile(file: File | null): string {
  if (!file) {
    return ''
  }
  const fileName = file.name.trim()
  const stripped = fileName.replace(/\.[^/.]+$/, '').trim()
  return stripped || fileName
}

function applyCatalogInstruments(melody: InstrumentId, left: InstrumentId) {
  melodyInstrument.value = melody
  leftHandInstrument.value = left
}

async function refreshCatalog() {
  catalogLoading.value = true
  try {
    catalogEntries.value = await listCatalogEntries()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '目录加载失败'
  } finally {
    catalogLoading.value = false
  }
}

async function playWithCurrentSettings(tempo: number, events: PlaybackEvent[]) {
  const filtered = filterPlaybackEvents(events, playbackMode.value)
  if (!filtered.length) {
    autoPlayMessage.value =
      playbackMode.value === 'left' ? '当前曲目无左手事件。' : '当前播放模式下没有可播放事件。'
    return
  }

  const warnings = await playScore({
    tempo,
    playbackEvents: events,
    mode: playbackMode.value,
    melodyInstrument: melodyInstrument.value,
    leftHandInstrument: leftHandInstrument.value,
  })
  autoPlayMessage.value = warnings[0] ?? ''
}

async function onRecognize() {
  if (!selectedFile.value) {
    errorMessage.value = '请先选择谱面文件。'
    recognizeStatus.value = '请选择文件后再识别。'
    return
  }

  loading.value = true
  errorMessage.value = ''
  autoPlayMessage.value = ''
  recognizeStatus.value = '识别中，请稍候...'

  try {
    const file = selectedFile.value
    const response = await recognizeScore(file)
    result.value = toRecognizeResponse(response)
    activeCatalogId.value = response.catalogEntryId
    applyCatalogInstruments(response.melodyInstrument, response.leftHandInstrument)
    await refreshCatalog()

    const preferredTitle = deriveTitleFromFile(file)
    if (preferredTitle && preferredTitle !== response.catalogTitle) {
      try {
        await updateCatalogEntry(response.catalogEntryId, { title: preferredTitle })
        await refreshCatalog()
      } catch {
        errorMessage.value = '默认曲目名更新失败，请手动重命名。'
      }
    }

    const playbackEvents =
      response.playbackEvents?.length ? response.playbackEvents : fallbackPlaybackEventsFromNotes(response.notes)

    if (playbackEvents.length) {
      try {
        await playWithCurrentSettings(response.tempo, playbackEvents)
      } catch (error) {
        autoPlayMessage.value =
          error instanceof Error ? error.message : '浏览器阻止了自动播放，请点击“播放”按钮。'
      }
    }

    recognizeStatus.value = '识别完成，可继续替换文件重新识别。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '识别失败'
    recognizeStatus.value = '识别失败，请检查文件后重试。'
    result.value = null
  } finally {
    loading.value = false
  }
}

async function onPlay() {
  if (!result.value || !resolvedPlaybackEvents.value.length) {
    return
  }
  await playWithCurrentSettings(result.value.tempo, resolvedPlaybackEvents.value)
}

async function onPlayFromCatalog(entryId: string) {
  errorMessage.value = ''
  autoPlayMessage.value = ''

  try {
    const detail: CatalogEntryDetail = await getCatalogEntry(entryId)
    result.value = detail.result
    activeCatalogId.value = detail.id
    applyCatalogInstruments(detail.melodyInstrument, detail.leftHandInstrument)
    const playbackEvents =
      detail.result.playbackEvents?.length
        ? detail.result.playbackEvents
        : fallbackPlaybackEventsFromNotes(detail.result.notes)
    await playWithCurrentSettings(detail.result.tempo, playbackEvents)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '播放失败'
  }
}

async function onDeleteFromCatalog(entryId: string) {
  errorMessage.value = ''

  try {
    await deleteCatalogEntry(entryId)
    if (activeCatalogId.value === entryId) {
      stopScore()
      activeCatalogId.value = null
      result.value = null
    }
    await refreshCatalog()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '删除失败'
  }
}

function onRequestResetCatalog() {
  confirmResetOpen.value = true
}

async function onConfirmResetCatalog() {
  resetLoading.value = true
  errorMessage.value = ''

  try {
    await resetCatalog('WIPE_CATALOG')
    stopScore()
    result.value = null
    activeCatalogId.value = null
    confirmResetOpen.value = false
    await refreshCatalog()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '目录重置失败'
  } finally {
    resetLoading.value = false
  }
}

async function onInstrumentChange(hand: 'melody' | 'left', value: InstrumentId) {
  const previousMelody = melodyInstrument.value
  const previousLeft = leftHandInstrument.value

  if (hand === 'melody') {
    melodyInstrument.value = value
  } else {
    leftHandInstrument.value = value
  }

  if (!activeCatalogId.value) {
    return
  }

  instrumentSaving.value = true
  errorMessage.value = ''
  try {
    await updateCatalogEntry(activeCatalogId.value, {
      melodyInstrument: melodyInstrument.value,
      leftHandInstrument: leftHandInstrument.value,
    })
    await refreshCatalog()
  } catch (error) {
    melodyInstrument.value = previousMelody
    leftHandInstrument.value = previousLeft
    errorMessage.value = error instanceof Error ? error.message : '音色保存失败，已回退显示'
  } finally {
    instrumentSaving.value = false
  }
}

function onStop() {
  stopScore()
}

function onStartRename(entryId: string, currentTitle: string) {
  editingCatalogId.value = entryId
  editingCatalogTitle.value = currentTitle
}

function onCancelRename() {
  editingCatalogId.value = null
  editingCatalogTitle.value = ''
}

async function onCommitRename(entryId: string, title: string) {
  const nextTitle = title.trim()
  const currentTitle = catalogEntries.value.find((entry) => entry.id === entryId)?.title ?? ''

  if (!nextTitle || nextTitle === currentTitle) {
    onCancelRename()
    return
  }

  try {
    await updateCatalogEntry(entryId, { title: nextTitle })
    await refreshCatalog()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重命名失败'
  } finally {
    onCancelRename()
  }
}

onMounted(() => {
  void refreshCatalog()
})
</script>

<template>
  <main class="screen">
    <section class="hero">
      <p class="kicker">Music It Stage</p>
      <h1>乐谱识别与自动回放台</h1>
      <p class="description">主区专注当前曲目与播放控制，目录与识别细节在两侧协同展示。</p>
      <button data-testid="open-recognize-dialog" type="button" class="open-dialog" @click="recognizeDialogOpen = true">
        上传并识别
      </button>
    </section>

    <section class="layout">
      <Disclosure as="aside" class="catalog-sidebar" :default-open="sidebarDefaultOpen" v-slot="{ open }">
        <div class="sidebar-head">
          <h2>历史目录</h2>
          <DisclosureButton data-testid="catalog-toggle" class="toggle">
            {{ open ? '收起目录' : '展开目录' }}
          </DisclosureButton>
        </div>

        <DisclosurePanel class="sidebar-panel">
          <CatalogList
            :entries="catalogEntries"
            :loading="catalogLoading"
            :active-id="activeCatalogId"
            :instrument-label-map="instrumentLabelMap"
            :editing-id="editingCatalogId"
            :editing-title="editingCatalogTitle"
            @play="onPlayFromCatalog"
            @delete="onDeleteFromCatalog"
            @start-rename="onStartRename"
            @update-editing-title="editingCatalogTitle = $event"
            @commit-rename="onCommitRename"
            @cancel-rename="onCancelRename"
          />

          <button
            type="button"
            class="reset-catalog"
            :disabled="catalogLoading || resetLoading"
            data-testid="catalog-reset"
            @click="onRequestResetCatalog"
          >
            {{ resetLoading ? '重置中...' : '清空目录' }}
          </button>
        </DisclosurePanel>
      </Disclosure>

      <section class="primary">
        <article class="current">
          <p class="label">当前播放曲目</p>
          <h2>{{ activeTitle }}</h2>
          <p class="status" v-if="result">Tempo {{ result.tempo }} BPM · 拍号 {{ result.timeSignature }}</p>
          <p class="status" v-else>尚未开始识别</p>
        </article>

        <PlaybackModeGroup v-model="playbackMode" />

        <div class="instrument-grid">
          <InstrumentListbox
            test-id-prefix="melody-instrument"
            label="主旋律音色"
            :model-value="melodyInstrument"
            :options="instrumentOptions"
            :disabled="instrumentSaving"
            @update:model-value="onInstrumentChange('melody', $event)"
          />
          <InstrumentListbox
            test-id-prefix="left-instrument"
            label="左手音色"
            :model-value="leftHandInstrument"
            :options="instrumentOptions"
            :disabled="instrumentSaving"
            @update:model-value="onInstrumentChange('left', $event)"
          />
        </div>

        <div class="player-actions">
          <button data-testid="main-play" type="button" class="play" :disabled="!canPlay" @click="onPlay">播放</button>
          <button data-testid="main-stop" type="button" class="stop" @click="onStop">停止</button>
        </div>

        <p class="hint">
          当前音色：旋律 {{ melodyInstrumentLabel }}，左手 {{ leftHandInstrumentLabel }}（切换后下次播放生效）
        </p>

        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        <p v-if="autoPlayMessage" class="hint">{{ autoPlayMessage }}</p>
      </section>

      <aside class="details">
        <h2>识别详情</h2>

        <template v-if="result">
          <div class="meta">
            <p>音符数 {{ result.notes.length }}</p>
            <p>播放事件 {{ resolvedPlaybackEvents.length }}</p>
            <p>引擎 {{ result.meta.engine }}</p>
          </div>

          <ul v-if="result.meta.warnings.length" class="warnings">
            <li v-for="warning in result.meta.warnings" :key="warning">{{ warning }}</li>
          </ul>

          <ResultTable :notes="result.notes" />
        </template>

        <p v-else class="empty">上传并识别后，这里会显示结构化音符明细。</p>
      </aside>
    </section>

    <RecognizeDialog
      v-model:open="recognizeDialogOpen"
      v-model:file="selectedFile"
      :loading="loading"
      :error-message="errorMessage"
      :status-message="recognizeStatus"
      @submit="onRecognize"
    />

    <ConfirmDialog
      v-model:open="confirmResetOpen"
      title="确认清空目录"
      description="将删除所有已识别曲目与缓存文件，该操作不可恢复。"
      :loading="resetLoading"
      confirm-text="确认清空"
      @confirm="onConfirmResetCatalog"
    />
  </main>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  color: #17143f;
}

.screen {
  --stage-bg: #f7f4ff;
  --panel-bg: #ffffff;
  --panel-border: #8d86cf;
  --primary-ink: #1e1a57;
  --sub-ink: #605a98;
  --accent: linear-gradient(130deg, #29237f, #de429f);
  --accent-soft: #ece7ff;

  min-height: 100vh;
  padding: 22px;
  background:
    radial-gradient(circle at 14% 16%, rgba(47, 185, 255, 0.18), transparent 30%),
    radial-gradient(circle at 83% 9%, rgba(247, 95, 192, 0.18), transparent 34%),
    linear-gradient(165deg, #f8f6ff, #f3f1ff 52%, #eff4ff);
  display: grid;
  gap: 18px;
}

.hero {
  border: 1px solid var(--panel-border);
  border-radius: 22px;
  padding: 18px 20px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 16px 30px rgba(45, 34, 127, 0.14);
  animation: appear 440ms ease-out;
  display: grid;
  gap: 8px;

  .kicker {
    margin: 0;
    color: #726ab0;
    letter-spacing: 0.14em;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
  }

  h1 {
    margin: 0;
    color: var(--primary-ink);
    font: 700 38px/1.06 'Noto Serif SC', serif;
  }

  .description {
    margin: 0;
    color: var(--sub-ink);
    max-width: 720px;
  }

  .open-dialog {
    justify-self: start;
    border: 0;
    border-radius: 12px;
    padding: 11px 16px;
    background: var(--accent);
    color: #fff;
    cursor: pointer;
    font-weight: 700;
    transition: transform 0.2s ease;

    &:hover {
      transform: translateY(-1px);
    }
  }
}

.layout {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(360px, 1fr) minmax(300px, 420px);
  gap: 14px;
  align-items: start;
}

.catalog-sidebar,
.primary,
.details {
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  background: var(--panel-bg);
  box-shadow: 0 16px 30px rgba(45, 34, 127, 0.12);
}

.catalog-sidebar {
  padding: 12px;
  display: grid;
  gap: 12px;

  .sidebar-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;

    h2 {
      margin: 0;
      color: var(--primary-ink);
      font: 700 23px/1.15 'Noto Serif SC', serif;
    }

    .toggle {
      border: 1px solid #8b83cd;
      border-radius: 999px;
      padding: 7px 12px;
      background: var(--accent-soft);
      color: #322c6e;
      cursor: pointer;
      font-weight: 600;
    }
  }

  .sidebar-panel {
    display: grid;
    gap: 12px;
  }

  .reset-catalog {
    border: 0;
    border-radius: 10px;
    padding: 10px;
    background: #ffe8f4;
    color: #8f205d;
    cursor: pointer;
    font-weight: 700;

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}

.primary {
  padding: 16px;
  display: grid;
  gap: 14px;

  .current {
    border: 1px solid #8f87d2;
    border-radius: 16px;
    background: linear-gradient(135deg, #2d277f, #df46a2);
    color: #fff;
    padding: 14px;
    display: grid;
    gap: 6px;

    .label {
      margin: 0;
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #e7ddff;
    }

    h2 {
      margin: 0;
      font: 700 28px/1.15 'Noto Serif SC', serif;
      word-break: break-word;
    }

    .status {
      margin: 0;
      color: #f2edff;
      font-weight: 500;
    }
  }

  .instrument-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .player-actions {
    display: flex;
    gap: 10px;

    button {
      border: 0;
      border-radius: 12px;
      padding: 11px 16px;
      cursor: pointer;
      font-weight: 700;
      transition: transform 0.2s ease, opacity 0.2s ease;

      &:hover:not(:disabled) {
        transform: translateY(-1px);
      }

      &:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
    }

    .play {
      background: var(--accent);
      color: #fff;
      flex: 1;
    }

    .stop {
      background: #ede9ff;
      color: #2b256f;
    }
  }

  .hint {
    margin: 0;
    color: #5e5898;
    font-size: 14px;
  }

  .error {
    margin: 0;
    color: #8f1f5f;
    font-weight: 700;
  }
}

.details {
  padding: 16px;
  display: grid;
  gap: 12px;

  h2 {
    margin: 0;
    color: var(--primary-ink);
    font: 700 24px/1.15 'Noto Serif SC', serif;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;

    p {
      margin: 0;
      border-radius: 999px;
      border: 1px solid #8f88d0;
      background: #f4f0ff;
      color: #2f2873;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
    }
  }

  .warnings {
    margin: 0;
    padding-left: 18px;
    color: #6e2353;
    display: grid;
    gap: 4px;
  }

  .empty {
    margin: 0;
    color: var(--sub-ink);
  }
}

@keyframes appear {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1180px) {
  .layout {
    grid-template-columns: minmax(230px, 280px) minmax(0, 1fr);
  }

  .details {
    grid-column: span 2;
  }
}

@media (max-width: 768px) {
  .screen {
    padding: 14px;
  }

  .hero {
    h1 {
      font-size: 30px;
    }
  }

  .layout {
    grid-template-columns: 1fr;
  }

  .details {
    grid-column: auto;
  }

  .primary {
    .instrument-grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>
