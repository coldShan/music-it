<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
import ResultTable from './components/ResultTable.vue'
import UploadField from './components/UploadField.vue'
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
const loading = ref(false)
const errorMessage = ref('')
const result = ref<RecognizeResponse | null>(null)
const autoPlayMessage = ref('')

const catalogEntries = ref<CatalogEntrySummary[]>([])
const catalogLoading = ref(false)
const activeCatalogId = ref<string | null>(null)
const resetLoading = ref(false)
const instrumentSaving = ref(false)
const playbackMode = ref<PlaybackMode>('both')
const melodyInstrument = ref<InstrumentId>('piano')
const leftHandInstrument = ref<InstrumentId>('piano')

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

async function promptRename(entryId: string, currentTitle: string) {
  const input = window.prompt('识别成功，请输入曲目名称', currentTitle)
  if (input === null) {
    return
  }

  const title = input.trim()
  if (!title || title === currentTitle) {
    return
  }

  await updateCatalogEntry(entryId, { title })
  await refreshCatalog()
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
    return
  }

  loading.value = true
  errorMessage.value = ''
  autoPlayMessage.value = ''

  try {
    const response = await recognizeScore(selectedFile.value)
    result.value = toRecognizeResponse(response)
    activeCatalogId.value = response.catalogEntryId
    applyCatalogInstruments(response.melodyInstrument, response.leftHandInstrument)
    await refreshCatalog()

    try {
      await promptRename(response.catalogEntryId, response.catalogTitle)
    } catch {
      errorMessage.value = '重命名失败，已保留默认标题。'
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
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '识别失败'
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

async function onResetCatalog() {
  if (!window.confirm('将清空已识别目录和缓存文件，是否继续？')) {
    return
  }

  resetLoading.value = true
  errorMessage.value = ''

  try {
    await resetCatalog('WIPE_CATALOG')
    stopScore()
    result.value = null
    activeCatalogId.value = null
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

onMounted(() => {
  void refreshCatalog()
})
</script>

<template>
  <main class="screen">
    <section class="panel">
      <header>
        <p class="kicker">Music It MVP</p>
        <h1>五线谱识别自动弹奏</h1>
        <p class="description">上传清晰谱面图片或 PDF，识别后立即以钢琴音色播放。</p>
      </header>

      <form class="controls" @submit.prevent="onRecognize">
        <UploadField v-model:file="selectedFile" />
        <button type="submit" :disabled="loading">
          {{ loading ? '识别中...' : '识别并自动弹奏' }}
        </button>
      </form>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      <p v-if="autoPlayMessage" class="hint">{{ autoPlayMessage }}</p>

      <CatalogList
        :entries="catalogEntries"
        :loading="catalogLoading"
        :active-id="activeCatalogId"
        :instrument-label-map="instrumentLabelMap"
        @play="onPlayFromCatalog"
        @delete="onDeleteFromCatalog"
      />

      <div class="catalog-tools">
        <button
          type="button"
          class="danger"
          :disabled="catalogLoading || resetLoading"
          data-testid="catalog-reset"
          @click="onResetCatalog"
        >
          {{ resetLoading ? '重置中...' : '清空旧目录（重置）' }}
        </button>
      </div>

      <section v-if="result" class="result">
        <div class="meta">
          <p>Tempo: {{ result.tempo }} BPM</p>
          <p>拍号: {{ result.timeSignature }}</p>
          <p>音符数: {{ result.notes.length }}</p>
          <p>播放事件数: {{ resolvedPlaybackEvents.length }}</p>
        </div>

        <div class="actions">
          <div class="mode-switch">
            <label for="playback-mode">播放声部</label>
            <select id="playback-mode" v-model="playbackMode">
              <option value="both">双手</option>
              <option value="right">只右手</option>
              <option value="left">只左手</option>
            </select>
          </div>
          <div class="mode-switch">
            <label for="melody-instrument">主旋律音色</label>
            <select
              id="melody-instrument"
              :value="melodyInstrument"
              :disabled="instrumentSaving"
              @change="onInstrumentChange('melody', ($event.target as HTMLSelectElement).value as InstrumentId)"
            >
              <option
                v-for="option in instrumentOptions"
                :key="`melody-${option.value}`"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="mode-switch">
            <label for="left-instrument">左手音色</label>
            <select
              id="left-instrument"
              :value="leftHandInstrument"
              :disabled="instrumentSaving"
              @change="onInstrumentChange('left', ($event.target as HTMLSelectElement).value as InstrumentId)"
            >
              <option
                v-for="option in instrumentOptions"
                :key="`left-${option.value}`"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </div>
          <button type="button" @click="onPlay" :disabled="!canPlay">播放</button>
          <button type="button" class="secondary" @click="onStop">停止</button>
        </div>

        <p class="hint">
          当前音色：旋律 {{ melodyInstrumentLabel }}，左手 {{ leftHandInstrumentLabel }}（切换后下次播放生效）
        </p>

        <ul v-if="result.meta.warnings.length" class="warnings">
          <li v-for="warning in result.meta.warnings" :key="warning">{{ warning }}</li>
        </ul>

        <ResultTable :notes="result.notes" />
      </section>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: 'IBM Plex Sans', sans-serif;
  color: #111;
}

.screen {
  min-height: 100vh;
  padding: 28px;
  background:
    radial-gradient(circle at 20% 20%, rgba(255, 226, 173, 0.28), transparent 45%),
    linear-gradient(145deg, #f6f1e6, #ddd3c2 60%, #d2c3ac);
  display: grid;
  place-items: center;

  .panel {
    width: min(900px, 100%);
    border-radius: 18px;
    padding: 26px;
    background: rgba(255, 252, 244, 0.9);
    border: 1px solid #9f9079;
    box-shadow: 0 12px 40px rgba(53, 33, 8, 0.16);
    animation: rise 420ms ease-out;
    display: grid;
    gap: 16px;

    header {
      margin-bottom: 2px;

      .kicker {
        margin: 0;
        font: 600 14px/1.2 'IBM Plex Sans', sans-serif;
        letter-spacing: 0.14em;
        color: #69583f;
      }

      h1 {
        margin: 8px 0;
        font: 600 44px/1.05 'Cormorant Garamond', serif;
      }

      .description {
        margin: 0;
        color: #4d453d;
      }
    }

    .controls {
      display: grid;
      gap: 14px;
      margin-bottom: 2px;
    }

    button {
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: #142139;
      color: #f7f4ec;
      cursor: pointer;
      font-weight: 600;
      transition: transform 0.2s ease, opacity 0.2s ease;

      &:hover:not(:disabled) {
        transform: translateY(-1px);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      &.secondary {
        background: #8a7f72;
      }
    }

    .error {
      color: #7f1f1f;
      margin: 0;
    }

    .hint {
      color: #5d503f;
      margin: 0;
    }

    .catalog-tools {
      display: flex;
      justify-content: flex-end;

      .danger {
        background: #7f2b2b;
      }
    }

    .result {
      display: grid;
      gap: 14px;

      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        color: #3b352d;
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;

        .mode-switch {
          display: flex;
          align-items: center;
          gap: 8px;

          label {
            color: #3b352d;
            font-size: 14px;
          }

          select {
            border: 1px solid #b8aa96;
            border-radius: 8px;
            padding: 8px 10px;
            background: #fff8ec;
            color: #1f1b15;
          }
        }
      }

      .warnings {
        margin: 0;
        padding-left: 18px;
        color: #4e402f;
      }
    }
  }
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .screen {
    padding: 16px;

    .panel {
      padding: 18px;

      header h1 {
        font-size: 34px;
      }
    }
  }
}
</style>
