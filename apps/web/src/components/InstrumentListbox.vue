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
  default: 'piano',
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
          <span class="arrow">▾</span>
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
              {{ option.label }}
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
    color: #4e4787;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .surface {
    position: relative;

    .button {
      width: 100%;
      border: 1px solid #8e87d0;
      border-radius: 12px;
      background: #fff;
      color: #211d57;
      padding: 10px 12px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }

    .options {
      position: absolute;
      z-index: 20;
      margin: 6px 0 0;
      width: 100%;
      border: 1px solid #8e87d0;
      border-radius: 12px;
      background: #fff;
      box-shadow: 0 16px 28px rgba(45, 34, 128, 0.2);
      list-style: none;
      padding: 8px;
      display: grid;
      gap: 4px;
      max-height: 220px;
      overflow-y: auto;

      .option {
        border-radius: 8px;
        padding: 8px 10px;
        color: #221f57;
        cursor: pointer;

        &.active {
          background: #efebff;
        }

        &.selected {
          font-weight: 700;
          color: #2c2488;
        }
      }
    }
  }
}
</style>
