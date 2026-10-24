<script setup lang="ts">
import { RadioGroup, RadioGroupLabel, RadioGroupOption } from '@headlessui/vue'
import type { PlaybackMode } from '../services/player'

const modeModel = defineModel<PlaybackMode>({
  default: 'both',
})

const options: Array<{ value: PlaybackMode; label: string }> = [
  { value: 'both', label: '双手' },
  { value: 'right', label: '右手' },
  { value: 'left', label: '左手' },
]
</script>

<template>
  <RadioGroup v-model="modeModel" class="playback-mode">
    <RadioGroupLabel class="group-label">播放声部</RadioGroupLabel>
    <div class="options">
      <RadioGroupOption
        v-for="option in options"
        :key="option.value"
        :value="option.value"
        as="template"
        v-slot="{ checked, active }"
      >
        <button
          type="button"
          :data-testid="`playback-mode-${option.value}`"
          :class="['option', { checked, active }]"
        >
          {{ option.label }}
        </button>
      </RadioGroupOption>
    </div>
  </RadioGroup>
</template>

<style scoped>
:global(.playback-mode) {
  display: grid;
  gap: 8px;

}

.playback-mode {
  .group-label {
    color: #76796f;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .options {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0;
    overflow: hidden;
    border: 1px solid #dedfd5;
    border-radius: 9px;
    background: #fffefa;

    .option {
      min-height: 38px;
      border: 0;
      border-right: 1px solid #dedfd5;
      padding: 8px;
      background: transparent;
      color: #76796f;
      cursor: pointer;
      font-weight: 650;
      transition: background .16s ease, color .16s ease;

      &:last-child { border-right: 0; }

      &.active {
        box-shadow: inset 0 0 0 2px #aab2a1;
      }

      &.checked {
        background: #556348;
        color: #fffefa;
      }
    }
  }
}

</style>
