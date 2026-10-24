<script setup lang="ts">
import { computed } from 'vue'
import type { PlaybackEvent } from '@music-it/shared-types'
import type { PlaybackMode } from '../services/player'
const props = defineProps<{ events: PlaybackEvent[]; beat: number; mode: PlaybackMode; durationBeats?: number | null }>()
const totalBeats = computed(() => props.events.reduce((end, event) => Math.max(end, event.startBeat + event.durationBeat), props.durationBeats ?? 0))
const windowStart = computed(() => Math.floor(Math.min(props.beat, Math.max(0, totalBeats.value - .001)) / 16) * 16)
const windowLength = computed(() => Math.min(16, Math.max(4, totalBeats.value - windowStart.value)))
const notes = computed(() => props.events.flatMap(event => event.midis.map(midi => ({ ...event, midi }))).filter(note => note.startBeat < windowStart.value + windowLength.value && note.startBeat + note.durationBeat > windowStart.value))
const pitchRange = computed(() => {
  let min = 48, max = 72
  for (const event of props.events) for (const midi of event.midis) { min = Math.min(min, midi); max = Math.max(max, midi) }
  return { min: min - 2, max: max + 2 }
})
const x = (beat: number) => 50 + (beat - windowStart.value) / windowLength.value * 900
</script>
<template>
  <div class="melody-preview">
    <svg viewBox="0 0 1000 260" role="img" :aria-label="`音符概览，第 ${windowStart + 1} 至 ${Math.ceil(windowStart + windowLength)} 拍，横向为时间，纵向为音高`">
      <defs><clipPath id="note-area"><rect x="50" y="20" width="900" height="210" /></clipPath></defs>
      <g class="staff-grid"><path v-for="line in 7" :key="line" :d="`M50 ${line * 30}H950`" /><path v-for="line in 5" :key="`v${line}`" :d="`M${50 + (line - 1) * 225} 20V220`" /></g>
      <g clip-path="url(#note-area)"><rect v-for="(note, index) in notes" :key="index" :x="x(Math.max(windowStart, note.startBeat))" :y="25 + (pitchRange.max - note.midi) / (pitchRange.max - pitchRange.min) * 180" :width="Math.max(3, (Math.min(windowStart + windowLength, note.startBeat + note.durationBeat) - Math.max(windowStart, note.startBeat)) / windowLength * 900 - 2)" height="7" rx="3.5" :class="['note', note.hand, { muted: mode !== 'both' && mode !== note.hand }]" /></g>
      <path v-if="beat > 0 && beat <= totalBeats" :d="`M${x(beat)} 20V220`" class="playhead" />
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
.playhead { stroke: #353e2e; stroke-width: 1.5; }.beat-label { fill: #82877c; font: 10px monospace; }
.preview-caption { display: flex; justify-content: space-between; gap: 12px; padding: 0 5%; color: #767b6f; font-size: 11px; }
.no-notes { position: absolute; top: 35%; left: 0; right: 0; text-align: center; color: #767b6f; }
</style>
