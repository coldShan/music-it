<script setup lang="ts">
import { RadioGroup, RadioGroupLabel, RadioGroupOption } from '@headlessui/vue'
import type { PlaybackMode } from '../services/player'

const modeModel = defineModel<PlaybackMode>({
  default: 'both',
})

const options: Array<{ value: PlaybackMode; label: string; description: string }> = [
  { value: 'both', label: '双手', description: '左右手' },
  { value: 'right', label: '只右手', description: '主旋律' },
  { value: 'left', label: '只左手', description: '伴奏线' },
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
          <span class="name">{{ option.label }}</span>
          <span class="description">{{ option.description }}</span>
        </button>
      </RadioGroupOption>
    </div>
  </RadioGroup>
</template>

<style scoped>
.playback-mode {
  display: grid;
  gap: 8px;

  .group-label {
    color: #4f4888;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .options {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;

    .option {
      border: 1px solid #8e87d0;
      border-radius: 12px;
      padding: 10px;
      background: #fff;
      color: #2a246b;
      cursor: pointer;
      text-align: left;
      display: grid;
      gap: 3px;
      transition: transform 0.2s ease, box-shadow 0.2s ease;

      .name {
        font-weight: 700;
      }

      .description {
        font-size: 12px;
        color: #5e5898;
      }

      &.active {
        box-shadow: 0 0 0 2px rgba(76, 56, 210, 0.16);
      }

      &.checked {
        background: linear-gradient(135deg, #2e2785, #dd3f9e);
        border-color: #2e2785;
        color: #fff;

        .description {
          color: #e6dcff;
        }
      }
    }
  }
}

@media (max-width: 900px) {
  .playback-mode {
    .options {
      grid-template-columns: 1fr;
    }
  }
}
</style>
