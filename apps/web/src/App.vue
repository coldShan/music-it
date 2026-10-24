<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { CatalogEntrySummary, InstrumentId, PlaybackEvent, RecognizeResponse } from '@music-it/shared-types'
import { instrumentOptions } from './constants/instruments'
import CatalogList from './components/CatalogList.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import InstrumentListbox from './components/InstrumentListbox.vue'
import PlaybackModeGroup from './components/PlaybackModeGroup.vue'
import RecognizeDialog from './components/RecognizeDialog.vue'
import ResultTable from './components/ResultTable.vue'
import ScorePreview from './components/ScorePreview.vue'
import { deleteCatalogEntry, getCatalogEntry, listCatalogEntries, recognizeScore, resetCatalog, updateCatalogEntry } from './services/api'
import { filterPlaybackEvents, getPlaybackSeconds, playScore, seekScore, stopScore, type PlaybackMode } from './services/player'
import './style.css'

const view = ref<'library' | 'studio'>('library')
const selectedFiles = ref<File[]>([])
const recognizeDialogOpen = ref(false)
const confirmResetOpen = ref(false)
const pendingDelete = ref<CatalogEntrySummary | null>(null)
const confirmDeleteOpen = computed({ get: () => !!pendingDelete.value, set: (open) => { if (!open) pendingDelete.value = null } })
const loading = ref(false)
const uploadProgress = ref<number | null>(0)
const importStatus = ref('')
const errorMessage = ref('')
const recognizeError = ref('')
const result = ref<RecognizeResponse | null>(null)
const autoPlayMessage = ref('')
const catalogEntries = ref<CatalogEntrySummary[]>([])
const catalogLoading = ref(false)
const catalogError = ref('')
const activeCatalogId = ref<string | null>(null)
const loadedTitle = ref('')
const entryLoading = ref(false)
const resetLoading = ref(false)
const deleteLoading = ref(false)
const instrumentSaving = ref(false)
const playbackMode = ref<PlaybackMode>('both')
const melodyInstrument = ref<InstrumentId>('toneSynth')
const leftHandInstrument = ref<InstrumentId>('toneSynth')
const settingsOpen = ref(false)
const editingCatalogId = ref<string | null>(null)
const editingCatalogTitle = ref('')
const search = ref('')
const sort = ref('recent')
const isPlaying = ref(false)
const playbackLoading = ref(false)
const elapsed = ref(0)
const playingDuration = ref(0)
let playbackTimer: ReturnType<typeof setInterval> | undefined
let selectionRequest = 0
let playRequest = 0

const visibleEntries = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return catalogEntries.value.filter(entry => entry.title.toLocaleLowerCase().includes(query)).sort((a, b) =>
    sort.value === 'title' ? a.title.localeCompare(b.title, 'zh-CN', { numeric: true }) : b.createdAt.localeCompare(a.createdAt),
  )
})
const activeTitle = computed(() => catalogEntries.value.find(entry => entry.id === activeCatalogId.value)?.title || loadedTitle.value || '当前曲目')
function fallbackEvents(notes: RecognizeResponse['notes']): PlaybackEvent[] {
  return notes.map(note => ({ ...note, pitches: [note.pitch], midis: [note.midi], hand: 'right', staff: '1', voice: '1' }))
}
const resolvedPlaybackEvents = computed(() => result.value?.playbackEvents?.length ? result.value.playbackEvents : fallbackEvents(result.value?.notes ?? []))
const canPlay = computed(() => !!resolvedPlaybackEvents.value.length && !loading.value && !entryLoading.value && !instrumentSaving.value)
function durationOf(events: PlaybackEvent[], tempo: number) {
  return events.reduce((end, event) => Math.max(end, event.startBeat + Math.max(event.durationBeat, event.gateBeat)), 0) * 60 / tempo
}
const duration = computed(() => result.value ? Math.max(durationOf(resolvedPlaybackEvents.value, result.value.tempo), (result.value.durationBeats ?? 0) * 60 / result.value.tempo) : 0)
const progress = computed(() => duration.value ? Math.min(100, elapsed.value / duration.value * 100) : 0)
function onSeek(event: Event) {
  if (!isPlaying.value || playbackLoading.value) return
  const seconds = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(seconds)) return
  elapsed.value = Math.max(0, Math.min(duration.value, seconds))
  seekScore(elapsed.value)
}
function formatTime(seconds: number) {
  const value = Math.max(0, Math.floor(seconds))
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`
}
function openRecognizeDialog() {
  recognizeError.value = ''
  recognizeDialogOpen.value = true
}
async function refreshCatalog() {
  catalogLoading.value = true
  catalogError.value = ''
  try { catalogEntries.value = await listCatalogEntries() }
  catch (error) { catalogError.value = error instanceof Error ? error.message : '曲库加载失败' }
  finally { catalogLoading.value = false }
}
function onStop() {
  playRequest += 1
  stopScore()
  clearInterval(playbackTimer)
  isPlaying.value = false
  playbackLoading.value = false
  elapsed.value = 0
}
async function onPlay() {
  if (!result.value || !canPlay.value || playbackLoading.value) return
  onStop()
  const request = playRequest
  const events = resolvedPlaybackEvents.value
  const filtered = filterPlaybackEvents(events, playbackMode.value)
  autoPlayMessage.value = ''
  if (!filtered.length) {
    autoPlayMessage.value = '这个声部没有可播放的音符，请尝试其他声部。'
    return
  }
  playbackLoading.value = true
  try {
    const warnings = await playScore({ tempo: result.value.tempo, playbackEvents: events, mode: playbackMode.value, melodyInstrument: melodyInstrument.value, leftHandInstrument: leftHandInstrument.value })
    if (request !== playRequest) return
    autoPlayMessage.value = warnings[0] ?? ''
    playingDuration.value = duration.value
    isPlaying.value = true
    playbackTimer = setInterval(() => {
      elapsed.value = getPlaybackSeconds()
      if (elapsed.value >= playingDuration.value + 0.1) {
        stopScore()
        clearInterval(playbackTimer)
        isPlaying.value = false
        elapsed.value = playingDuration.value
      }
    }, 100)
  } catch (error) {
    if (request === playRequest) autoPlayMessage.value = error instanceof Error ? error.message : '播放失败，请重试。'
  } finally { if (request === playRequest) playbackLoading.value = false }
}
async function onRecognize(force = false) {
  if (loading.value || !selectedFiles.value.length) return
  loading.value = true
  uploadProgress.value = 0
  importStatus.value = '正在上传乐谱…'
  recognizeError.value = ''
  errorMessage.value = ''
  onStop()
  selectionRequest += 1
  entryLoading.value = false
  try {
    const files = [...selectedFiles.value]
    const response = await recognizeScore(files, force, (percent) => {
      uploadProgress.value = percent === 100 ? null : percent
      importStatus.value = percent === 100
        ? '正在识别谱面，复杂乐谱可能需要几分钟。'
        : '正在上传乐谱…'
    })
    uploadProgress.value = null
    importStatus.value = '识别完成，正在整理曲库…'
    result.value = response
    activeCatalogId.value = response.catalogEntryId
    loadedTitle.value = response.catalogTitle
    melodyInstrument.value = response.melodyInstrument
    leftHandInstrument.value = response.leftHandInstrument
    const preferredTitle = files[0].name.replace(/\.[^/.]+$/, '').trim()
    if (!force && !response.isReused && preferredTitle && preferredTitle !== response.catalogTitle) {
      try {
        await updateCatalogEntry(response.catalogEntryId, { title: preferredTitle })
        loadedTitle.value = preferredTitle
      } catch { errorMessage.value = '乐谱已保存，但曲名更新失败，可在曲库中重命名。' }
    }
    await refreshCatalog()
    view.value = 'studio'
    settingsOpen.value = false
    autoPlayMessage.value = ''
    recognizeDialogOpen.value = false
    selectedFiles.value = []
  } catch (error) { recognizeError.value = error instanceof Error ? error.message : '识别失败，请重试。' }
  finally { loading.value = false }
}
async function openEntry(entryId: string, autoplay = false) {
  const request = ++selectionRequest
  onStop()
  entryLoading.value = true
  errorMessage.value = ''
  autoPlayMessage.value = ''
  try {
    const detail = await getCatalogEntry(entryId)
    if (request !== selectionRequest) return
    result.value = detail.result
    activeCatalogId.value = detail.id
    loadedTitle.value = detail.title
    melodyInstrument.value = detail.melodyInstrument
    leftHandInstrument.value = detail.leftHandInstrument
    view.value = 'studio'
    settingsOpen.value = false
    entryLoading.value = false
    if (autoplay) await onPlay()
  } catch (error) {
    if (request === selectionRequest) errorMessage.value = error instanceof Error ? error.message : '曲目加载失败'
  } finally { if (request === selectionRequest) entryLoading.value = false }
}
async function onConfirmDelete() {
  if (!pendingDelete.value || deleteLoading.value) return
  deleteLoading.value = true
  errorMessage.value = ''
  try {
    const entryId = pendingDelete.value.id
    await deleteCatalogEntry(entryId)
    if (activeCatalogId.value === entryId) { onStop(); activeCatalogId.value = null; result.value = null; view.value = 'library' }
    pendingDelete.value = null
    await refreshCatalog()
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : '删除失败' }
  finally { deleteLoading.value = false }
}
async function onConfirmResetCatalog() {
  if (resetLoading.value) return
  resetLoading.value = true
  errorMessage.value = ''
  try {
    await resetCatalog('WIPE_CATALOG')
    selectionRequest += 1
    onStop()
    result.value = null
    activeCatalogId.value = null
    confirmResetOpen.value = false
    view.value = 'library'
    await refreshCatalog()
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : '曲库清空失败' }
  finally { resetLoading.value = false }
}
async function onInstrumentChange(hand: 'melody' | 'left', value: InstrumentId) {
  if (instrumentSaving.value) return
  const previousMelody = melodyInstrument.value
  const previousLeft = leftHandInstrument.value
  if (hand === 'melody') melodyInstrument.value = value
  else leftHandInstrument.value = value
  if (!activeCatalogId.value) return
  const entryId = activeCatalogId.value
  instrumentSaving.value = true
  errorMessage.value = ''
  try {
    await updateCatalogEntry(entryId, { melodyInstrument: melodyInstrument.value, leftHandInstrument: leftHandInstrument.value })
    await refreshCatalog()
  } catch (error) {
    if (entryId === activeCatalogId.value) { melodyInstrument.value = previousMelody; leftHandInstrument.value = previousLeft }
    errorMessage.value = error instanceof Error ? error.message : '音色保存失败，已恢复原设置'
  } finally { instrumentSaving.value = false }
}
function onStartRename(entryId: string, title: string) { editingCatalogId.value = entryId; editingCatalogTitle.value = title }
function onCancelRename() { editingCatalogId.value = null; editingCatalogTitle.value = '' }
async function onCommitRename(entryId: string, title: string) {
  const nextTitle = title.trim()
  if (!nextTitle || nextTitle === catalogEntries.value.find(entry => entry.id === entryId)?.title) { onCancelRename(); return }
  try {
    await updateCatalogEntry(entryId, { title: nextTitle })
    await refreshCatalog()
    onCancelRename()
  } catch (error) { errorMessage.value = error instanceof Error ? error.message : '重命名失败，请重试' }
}
watch(view, () => { window.scrollTo({ top: 0, behavior: 'instant' }) })
watch(playbackMode, onStop)
onMounted(() => { void refreshCatalog() })
onUnmounted(() => { selectionRequest += 1; onStop() })
</script>

<template>
  <div class="app-shell" :class="{ 'has-player': result }">
    <header class="site-header">
      <a href="#" class="brand" aria-label="Music It 首页" @click.prevent="view = 'library'">
        <span class="brand-mark" aria-hidden="true">m<span>ı</span></span><span>music it<span class="brand-dot">.</span></span>
      </a>
      <nav aria-label="主导航">
        <button :class="{ selected: view === 'library' }" :aria-current="view === 'library' ? 'page' : undefined" @click="view = 'library'">我的曲库</button>
        <button :class="{ selected: view === 'studio' }" :aria-current="view === 'studio' ? 'page' : undefined" :disabled="!result" @click="view = 'studio'">试听室</button>
      </nav>
      <span class="header-note">A LITTLE SPACE FOR MUSIC</span>
    </header>

    <main id="main-content" class="workspace">
      <div v-if="errorMessage" class="notice error-notice" role="alert"><span>{{ errorMessage }}</span><button aria-label="关闭提示" @click="errorMessage = ''">×</button></div>
      <div v-if="entryLoading" class="notice" role="status">正在打开乐谱…</div>

      <template v-if="view === 'library'">
        <section class="page-heading"><div><p class="eyebrow">YOUR PERSONAL COLLECTION</p><h1>我的曲库<span class="heading-dot">.</span></h1></div><span class="collection-note">让每一张乐谱，都能被听见。</span></section>
        <section class="welcome" :class="{ 'has-collection': catalogEntries.length }">
          <div class="welcome-copy">
            <p class="eyebrow">FROM PAPER TO MELODY</p>
            <h2>纸上的音符，<br>耳边的旋律。</h2>
            <p class="welcome-description">导入你的乐谱，把旋律交给 Music It。<br>聆听全曲，也可以一次只练一只手。</p>
            <button class="button primary" data-testid="open-recognize-dialog" @click="openRecognizeDialog"><span aria-hidden="true">＋</span> 导入乐谱 <span aria-hidden="true">↗</span></button>
            <p class="format-hint">PNG、JPG 或 PDF · 支持多页图片</p>
          </div>
          <div class="score-art" aria-hidden="true">
            <div class="art-circle"></div>
            <div class="paper-sheet">
              <div class="paper-heading"><span>Music It</span><span>NO. 001</span></div>
              <p class="paper-title">A quiet little melody</p><p class="paper-subtitle">Andante · con amore</p>
              <svg viewBox="0 0 360 180" fill="none"><g stroke="currentColor" stroke-width=".8" opacity=".4"><path d="M15 35H345M15 45H345M15 55H345M15 65H345M15 75H345M15 115H345M15 125H345M15 135H345M15 145H345M15 155H345"/><path d="M125 35V75M235 35V75M345 35V75M125 115V155M235 115V155M345 115V155"/></g><g fill="currentColor"><ellipse cx="65" cy="65" rx="6" ry="4" transform="rotate(-20 65 65)"/><ellipse cx="95" cy="55" rx="6" ry="4"/><ellipse cx="150" cy="60" rx="6" ry="4"/><ellipse cx="180" cy="50" rx="6" ry="4"/><ellipse cx="210" cy="45" rx="6" ry="4"/><ellipse cx="265" cy="55" rx="6" ry="4"/><ellipse cx="310" cy="65" rx="6" ry="4"/><ellipse cx="65" cy="140" rx="6" ry="4"/><ellipse cx="95" cy="130" rx="6" ry="4"/><ellipse cx="150" cy="135" rx="6" ry="4"/><ellipse cx="180" cy="125" rx="6" ry="4"/><ellipse cx="210" cy="135" rx="6" ry="4"/><ellipse cx="265" cy="145" rx="6" ry="4"/><ellipse cx="310" cy="135" rx="6" ry="4"/></g><g stroke="currentColor" stroke-width="1.5"><path d="M70 65V36L100 26V55M155 60V31L185 21V50M215 45V17M270 55V27M315 65V37M70 140V111L100 101V130M155 135V106L185 96V125M215 135V107M270 145V117M315 135V107"/></g><text x="19" y="66" fill="currentColor" font-family="serif" font-size="32">𝄞</text><text x="19" y="149" fill="currentColor" font-family="serif" font-size="32">𝄢</text></svg>
              <div class="paper-footer"><span>PERFORM AT YOUR OWN PACE</span><span>01</span></div>
            </div>
            <span class="art-caption">a score, a sound, a moment.</span>
          </div>
        </section>

        <section class="library-section" aria-labelledby="library-title">
          <div class="library-toolbar"><h2 id="library-title">乐谱收藏 <span>{{ catalogEntries.length.toString().padStart(2, '0') }}</span></h2><div class="library-tools">
            <label class="search-field"><span aria-hidden="true">⌕</span><input v-model="search" type="search" placeholder="搜索曲名" aria-label="搜索曲名" data-testid="catalog-search"></label>
            <select v-model="sort" aria-label="曲目排序"><option value="recent">最近导入</option><option value="title">曲名排序</option></select>
          </div></div>
          <div v-if="catalogError" class="catalog-feedback" role="alert"><h3>暂时无法加载曲库</h3><p>{{ catalogError }}</p><button class="button secondary" @click="refreshCatalog">重新加载</button></div>
          <div v-else-if="!catalogLoading && !catalogEntries.length" class="first-score"><span class="empty-symbol" aria-hidden="true">♫</span><div><h3>第一首，就从你喜欢的开始。</h3><p>导入的乐谱会自动保存在这里，随时回来聆听。</p></div><button class="text-button" @click="openRecognizeDialog">导入第一首乐谱 ↗</button></div>
          <div v-else-if="!catalogLoading && !visibleEntries.length" class="catalog-feedback"><h3>没有找到「{{ search }}」</h3><button class="text-button" @click="search = ''">清除搜索</button></div>
          <CatalogList v-else :entries="visibleEntries" :loading="catalogLoading" :active-id="activeCatalogId" :editing-id="editingCatalogId" :editing-title="editingCatalogTitle"
            @select="openEntry($event)" @play="openEntry($event, true)" @delete="errorMessage = ''; pendingDelete = catalogEntries.find(entry => entry.id === $event) ?? null" @start-rename="onStartRename" @update-editing-title="editingCatalogTitle = $event" @commit-rename="onCommitRename" @cancel-rename="onCancelRename" />
          <div v-if="catalogEntries.length" class="library-footer"><span>共 {{ catalogEntries.length }} 首 · 已识别乐谱自动保存</span><details class="library-manage"><summary>管理曲库</summary><button class="text-button danger" data-testid="catalog-reset" :disabled="catalogLoading || resetLoading || entryLoading" @click="errorMessage = ''; confirmResetOpen = true">清空所有曲目</button></details></div>
        </section>
      </template>

      <template v-else-if="result">
        <div class="studio-breadcrumb"><button class="text-button" @click="view = 'library'">← 返回曲库</button><button class="text-button" data-testid="open-recognize-dialog" @click="openRecognizeDialog">＋ 导入另一首</button></div>
        <section class="studio-heading"><p class="eyebrow">THE LISTENING ROOM</p><h1>{{ activeTitle }}</h1><div class="score-facts"><span>{{ result.tempo }} <small>BPM</small></span><i></i><span>{{ result.timeSignature }} <small>拍</small></span><i></i><span>{{ formatTime(duration) }} <small>时长</small></span></div></section>
        <section class="listening-surface" aria-label="曲目试听">
          <div class="preview-header"><div><p class="eyebrow">MELODY AT A GLANCE</p><h2>看见旋律的起伏</h2></div><span class="voice-key"><i></i>右手 <i></i>左手</span></div>
          <div class="practice-controls"><PlaybackModeGroup v-model="playbackMode" /><button class="settings-toggle" data-testid="settings-toggle" :aria-expanded="settingsOpen" aria-controls="sound-settings" @click="settingsOpen = !settingsOpen">音色设置 <span aria-hidden="true">{{ settingsOpen ? '−' : '＋' }}</span></button></div>
          <div v-if="settingsOpen" id="sound-settings" class="sound-settings">
            <InstrumentListbox test-id-prefix="melody-instrument" label="右手 · 主旋律" :model-value="melodyInstrument" :options="instrumentOptions" :disabled="instrumentSaving" @update:model-value="onInstrumentChange('melody', $event)" />
            <InstrumentListbox test-id-prefix="left-instrument" label="左手 · 伴奏" :model-value="leftHandInstrument" :options="instrumentOptions" :disabled="instrumentSaving" @update:model-value="onInstrumentChange('left', $event)" />
            <p>{{ instrumentSaving ? '正在保存音色…' : '音色会为这首曲目保存，下次播放时生效。' }}</p>
          </div>
          <ScorePreview :events="resolvedPlaybackEvents" :duration-beats="result.durationBeats" :beat="elapsed * result.tempo / 60" :mode="playbackMode" />
        </section>
        <p class="practice-hint">{{ isPlaying ? '正在聆听。切换声部会停止播放；音色更改在下次播放时生效。' : '点击下方播放开始聆听，或选择一个声部单独练习。' }}</p>
        <div v-if="!canPlay && !entryLoading && !loading" class="notice" role="status">这份乐谱没有可播放的音符。可以查看识别详情，或换一张更清晰的谱面重新导入。</div>
        <p v-if="result.meta.rhythmIssues?.length" class="notice" role="status">部分小节的节奏或拍号未能可靠识别，请对照原谱核对。可在识别详情中查看位置，或重新导入更清晰的谱面。</p>
        <details class="recognition-details" data-testid="recognition-details"><summary>识别详情 <span>{{ result.meta.warnings.length ? `${result.meta.warnings.length} 条识别提示` : '查看音符与识别信息' }}</span></summary><div class="diagnostics"><p class="diagnostic-meta">音符数 {{ result.notes.length }} · 播放事件 {{ resolvedPlaybackEvents.length }} · 引擎 {{ result.meta.engine }}</p><ul v-if="result.meta.warnings.length" class="warnings"><li v-for="warning in result.meta.warnings" :key="warning">{{ warning }}</li></ul><ResultTable :notes="result.notes" /></div></details>
      </template>
      <footer class="page-footer"><span>MUSIC IT / 乐谱与声音之间</span><span>Take a moment. Make some music.</span></footer>
    </main>

    <section v-if="result" class="player-dock" :class="{ 'is-playing': isPlaying }" aria-label="播放器">
      <div v-if="autoPlayMessage" class="playback-notice" role="status">{{ autoPlayMessage }}</div>
      <div class="dock-inner">
        <button class="dock-track" title="查看当前乐谱" @click="view = 'studio'">
          <span class="track-symbol" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none"><path d="M8 12h24M8 17h24M8 22h24M8 27h24" stroke="currentColor" opacity=".2"/><path d="M24 24V10l-10 3v14M14 17l10-3" stroke="currentColor" stroke-width="1.6"/><ellipse cx="11" cy="27" rx="3.5" ry="2.5" fill="currentColor"/><ellipse cx="21" cy="24" rx="3.5" ry="2.5" fill="currentColor"/></svg></span>
          <span class="track-copy"><strong>{{ activeTitle }}</strong><small><i class="playback-dot" aria-hidden="true"></i>{{ isPlaying ? '正在播放' : playbackLoading ? '正在准备音色…' : '准备聆听' }}</small></span>
        </button>
        <div class="dock-playback">
          <div class="transport">
            <span class="transport-caption">{{ isPlaying ? '聆听此刻' : '让旋律响起' }}</span>
            <button v-if="!isPlaying" data-testid="main-play" class="play-button" :disabled="!canPlay || playbackLoading" :aria-label="playbackLoading ? '正在准备音色' : '播放'" :title="playbackLoading ? '正在准备音色' : '播放'" @click="onPlay"><span v-if="playbackLoading" class="loading-ring" aria-hidden="true"></span><svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5.5v13l10-6.5Z" fill="currentColor"/></svg></button>
            <button v-else class="play-button" data-testid="main-stop" aria-label="停止" title="停止播放" @click="onStop"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor"/></svg></button>
            <button v-if="playbackLoading" class="transport-caption cancel-playback" @click="onStop">取消</button><span v-else class="transport-caption">{{ isPlaying ? '停止播放' : '点击播放' }}</span>
          </div>
          <div class="track-progress"><span>{{ formatTime(elapsed) }}</span><input class="seek-slider" type="range" min="0" :max="duration" step="0.1" :value="elapsed" :disabled="!isPlaying || playbackLoading || !duration" :style="{ '--progress': `${progress}%` }" aria-label="播放进度" :aria-valuetext="`${formatTime(elapsed)} / ${formatTime(duration)}`" @input="onSeek" /><span>{{ formatTime(duration) }}</span></div>
        </div>
        <div class="dock-details"><span class="dock-mode">{{ playbackMode === 'both' ? '双手合奏' : playbackMode === 'left' ? '左手练习' : '右手练习' }}</span><span class="dock-tempo">{{ result.tempo }} <small>BPM</small><i aria-hidden="true">·</i>{{ result.timeSignature }}</span></div>
      </div>
    </section>
    <RecognizeDialog v-if="recognizeDialogOpen" v-model:open="recognizeDialogOpen" v-model:files="selectedFiles" :loading="loading" :error-message="recognizeError" :upload-progress="uploadProgress" :status-message="loading ? importStatus : ''" @submit="onRecognize" />
    <ConfirmDialog v-model:open="confirmResetOpen" title="清空整个曲库？" :error-message="errorMessage" description="所有已识别的曲目与缓存文件都会被删除，此操作无法撤销。" :loading="resetLoading" confirm-text="清空曲库" @confirm="onConfirmResetCatalog" />
    <ConfirmDialog v-model:open="confirmDeleteOpen" title="删除这首乐谱？" :error-message="errorMessage" :description="`「${pendingDelete?.title ?? ''}」及其识别结果会被删除，此操作无法撤销。`" :loading="deleteLoading" confirm-text="删除乐谱" @confirm="onConfirmDelete" />
  </div>
</template>
