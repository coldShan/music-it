<script setup lang="ts">
import type { RecognizedNote } from '@music-it/shared-types'

defineProps<{
  notes: RecognizedNote[]
}>()
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>音名</th>
          <th>MIDI</th>
          <th>起始拍</th>
          <th>时值(拍)</th>
          <th>发音时值(拍)</th>
          <th>断句</th>
          <th>奏法</th>
          <th>小节</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(note, index) in notes" :key="`${note.pitch}-${note.startBeat}-${index}`">
          <td>{{ note.pitch }}</td>
          <td>{{ note.midi }}</td>
          <td>{{ note.startBeat }}</td>
          <td>{{ note.durationBeat }}</td>
          <td>{{ note.gateBeat }}</td>
          <td>{{ note.phraseBreakAfter ? '是' : '否' }}</td>
          <td>{{ note.articulation }}</td>
          <td>{{ note.sourceMeasure }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  position: relative;
  z-index: 0;
  isolation: isolate;
  overflow: auto;
  border: 1px solid #dedfd5;
  border-radius: 10px;
  background: #fffefa;
  max-height: 460px;

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    color: #4c5048;

    th,
    td {
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid #e9e9e2;
      font-variant-numeric: tabular-nums;
    }

    thead th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #f1f0eb;
      color: #252923;
      font-weight: 700;
      letter-spacing: 0.02em;
    }

    tbody tr:hover {
      background: #f5f5f0;
    }
  }
}
</style>
