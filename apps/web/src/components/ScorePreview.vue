<script setup lang="ts">
import { computed } from 'vue'
import type { PlaybackEvent } from '@music-it/shared-types'
import type { PlaybackMode } from '../services/player'
type PracticeView = { beat: number; target: number[]; hits: number[]; wrong: number | null }
const props = defineProps<{ events: PlaybackEvent[]; beat: number; mode: PlaybackMode; durationBeats?: number | null; practice?: PracticeView | null }>()
const viewBeat = computed(() => props.practice ? props.practice.beat : props.beat)
const totalBeats = computed(() => props.events.reduce((end, event) => Math.max(end, event.startBeat + event.durationBeat), props.durationBeats ?? 0))
const windowStart = computed(() => Math.floor(Math.min(viewBeat.value, Math.max(0, totalBeats.value - .001)) / 16) * 16)
const windowLength = computed(() => Math.min(16, Math.max(4, totalBeats.value - windowStart.value)))
function practiceClass(note: { startBeat: number; midi: number }) {
  if (!props.practice) return ''
  if (Math.round(note.startBeat * 1000) !== Math.round(props.practice.beat * 1000)) return ''
  if (props.practice.hits.includes(note.midi)) return 'hit'
  if (props.practice.target.includes(note.midi)) return 'target'
  return ''
}
const notes = computed(() => props.events.flatMap(event => event.midis.map(midi => ({ ...event, midi }))).filter(note => note.startBeat < windowStart.value + windowLength.value && note.startBeat + note.durationBeat > windowStart.value).map(note => ({ ...note, mark: practiceClass(note) })))
const pitchRange = computed(() => {
  let min = 48, max = 72
  for (const event of props.events) for (const midi of event.midis) { min = Math.min(min, midi); max = Math.max(max, midi) }
  return { min: min - 2, max: max + 2 }
})
const wrongY = computed(() => {
  if (!props.practice || props.practice.wrong === null) return null
  const midi = Math.min(pitchRange.value.max, Math.max(pitchRange.value.min, props.practice.wrong))
  return 25 + (pitchRange.value.max - midi) / (pitchRange.value.max - pitchRange.value.min) * 180
})
const showPlayhead = computed(() => props.practice
  ? viewBeat.value >= 0 && viewBeat.value <= totalBeats.value
  : viewBeat.value > 0 && viewBeat.value <= totalBeats.value)
const x = (beat: number) => 50 + (beat - windowStart.value) / windowLength.value * 900
</script>
<template>
  <div class="melody-preview">
    <svg viewBox="0 0 1000 260" role="img" :aria-label="`音符概览，第 ${windowStart + 1} 至 ${Math.ceil(windowStart + windowLength)} 拍，横向为时间，纵向为音高`">
      <defs><clipPath id="note-area"><rect x="50" y="20" width="900" height="210" /></clipPath></defs>
      <g class="staff-grid"><path v-for="line in 7" :key="line" :d="`M50 ${line * 30}H950`" /><path v-for="line in 5" :key="`v${line}`" :d="`M${50 + (line - 1) * 225} 20V220`" /></g>
      <g clip-path="url(#note-area)"><rect v-for="(note, index) in notes" :key="index" :x="x(Math.max(windowStart, note.startBeat))" :y="25 + (pitchRange.max - note.midi) / (pitchRange.max - pitchRange.min) * 180" :width="Math.max(3, (Math.min(windowStart + windowLength, note.startBeat + note.durationBeat) - Math.max(windowStart, note.startBeat)) / windowLength * 900 - 2)" height="7" rx="3.5" :class="['note', note.hand, note.mark, { muted: mode !== 'both' && mode !== note.hand }]" /></g>
      <path v-if="showPlayhead" :d="`M${x(viewBeat)} 20V220`" class="playhead" />
      <path v-if="wrongY !== null" :d="`M${x(viewBeat) - 7} ${wrongY}H${x(viewBeat) + 7}`" class="wrong-marker" />
      <text v-for="index in 5" :key="`label${index}`" :x="50 + (index - 1) * 225" y="247" class="beat-label">{{ +(windowStart + (index - 1) * windowLength / 4).toFixed(1) }}</text>
    </svg>
    <p v-if="!events.length" class="no-notes">还没有识别到可播放的音符</p>
    <div class="preview-caption"><span>音高 / 时间（拍）</span><span>第 {{ windowStart + 1 }}–{{ Math.ceil(windowStart + windowLength) }} 拍 · 随播放翻页</span></div>
  </div>
</template>
<style scoped>
.melody-preview { position: relative; padding: 20px 0 12px; }
svg { display: block; width: 100%; min-height: 150px; }
.staff-grid { fill: none; stroke: #e7e7de; stroke-width: 1; }
.note { fill: #627454; }.note.left { fill: #ba9c72; }.note.muted { opacity: .16; }
.note.target { fill: #cdd8bd; stroke: #3f4a36; stroke-width: 1.2; }
.note.hit { fill: #627454; stroke: #627454; stroke-width: 1; }
.playhead { stroke: #353e2e; stroke-width: 1.5; }
.wrong-marker { stroke: #b5543c; stroke-width: 2; stroke-linecap: round; }
.beat-label { fill: #82877c; font: 10px monospace; }
.preview-caption { display: flex; justify-content: space-between; gap: 12px; padding: 0 5%; color: #767b6f; font-size: 11px; }
.no-notes { position: absolute; top: 35%; left: 0; right: 0; text-align: center; color: #767b6f; }
</style>
