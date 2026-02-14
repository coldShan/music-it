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
          <th>小节</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(note, index) in notes" :key="`${note.pitch}-${note.startBeat}-${index}`">
          <td>{{ note.pitch }}</td>
          <td>{{ note.midi }}</td>
          <td>{{ note.startBeat }}</td>
          <td>{{ note.durationBeat }}</td>
          <td>{{ note.sourceMeasure }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
  border: 1px solid #9c907f;
  border-radius: 12px;
  background: #fffdf8;

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;

    th,
    td {
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid #e7dfd2;
    }

    thead th {
      background: #efe7da;
      font-weight: 600;
    }
  }
}
</style>
