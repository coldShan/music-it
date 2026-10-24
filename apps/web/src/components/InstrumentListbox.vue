<script setup lang="ts">
import { computed } from 'vue'
import {
  Listbox,
  ListboxButton,
  ListboxLabel,
  ListboxOption,
  ListboxOptions,
} from '@headlessui/vue'
import type { InstrumentId } from '@music-it/shared-types'

const model = defineModel<InstrumentId>({
  default: 'toneSynth',
})

const props = withDefaults(
  defineProps<{
    label: string
    options: Array<{ value: InstrumentId; label: string }>
    disabled?: boolean
    testIdPrefix?: string
  }>(),
  {
    disabled: false,
    testIdPrefix: 'instrument',
  },
)

const selectedLabel = computed(() => {
  const found = props.options.find((option) => option.value === model.value)
  return found?.label ?? '未选择'
})
</script>

<template>
  <Listbox v-model="model" :disabled="disabled">
    <div class="instrument-listbox">
      <ListboxLabel class="label">{{ label }}</ListboxLabel>
      <div class="surface">
        <ListboxButton :data-testid="`${testIdPrefix}-button`" class="button">
          <span>{{ selectedLabel }}</span>
          <span class="arrow" aria-hidden="true">⌄</span>
        </ListboxButton>
        <ListboxOptions class="options">
          <ListboxOption
            v-for="option in options"
            :key="option.value"
            :value="option.value"
            as="template"
            v-slot="{ active, selected }"
          >
            <li
              :data-testid="`${testIdPrefix}-option-${option.value}`"
              :class="['option', { active, selected }]"
            >
              <span>{{ option.label }}</span>
              <span v-if="selected" aria-hidden="true">✓</span>
            </li>
          </ListboxOption>
        </ListboxOptions>
      </div>
    </div>
  </Listbox>
</template>

<style scoped>
.instrument-listbox {
  display: grid;
  gap: 8px;

  .label {
    color: #76796f;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .surface {
    position: relative;

    .button {
      width: 100%;
      min-height: 40px;
      border: 1px solid #dedfd5;
      border-radius: 9px;
      background: #fffefa;
      color: #252923;
      padding: 8px 11px;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      transition: border-color .16s ease;

      &:hover:not(:disabled) { border-color: #bfc3b7; }
      &:disabled { opacity: .55; cursor: not-allowed; }
      .arrow { color: #76796f; font-size: 16px; }
    }

    .options {
      position: absolute;
      z-index: 20;
      margin: 5px 0 0;
      width: 100%;
      border: 1px solid #dedfd5;
      border-radius: 9px;
      background: #fffefa;
      box-shadow: 0 12px 28px rgba(37, 41, 35, .12);
      list-style: none;
      padding: 5px;
      display: grid;
      gap: 4px;
      max-height: 220px;
      overflow-y: auto;

      .option {
        display: flex;
        justify-content: space-between;
        border-radius: 6px;
        padding: 8px 9px;
        color: #4e524a;
        cursor: pointer;

        &.active {
          background: #f0f1eb;
        }

        &.selected {
          font-weight: 700;
          color: #556348;
        }
      }
    }
  }
}
</style>
