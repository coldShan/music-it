<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'

const openModel = defineModel<boolean>('open', {
  default: false,
})

const props = withDefaults(
  defineProps<{
    title: string
    description: string
    loading?: boolean
    confirmText?: string
    cancelText?: string
  }>(),
  {
    loading: false,
    confirmText: '确认',
    cancelText: '取消',
  },
)

const emit = defineEmits<{
  confirm: []
}>()

function close() {
  if (props.loading) {
    return
  }
  if (!openModel.value) {
    return
  }
  openModel.value = false
}

function onConfirm() {
  emit('confirm')
}
</script>

<template>
  <TransitionRoot :show="openModel" as="template">
    <Dialog class="confirm-dialog" @close="close">
      <TransitionChild
        as="template"
        enter="ease-out duration-220"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-160"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="overlay" />
      </TransitionChild>

      <div class="dialog-wrap">
        <TransitionChild
          as="template"
          enter="ease-out duration-220"
          enter-from="opacity-0 translate-y-5 scale-95"
          enter-to="opacity-100 translate-y-0 scale-100"
          leave="ease-in duration-160"
          leave-from="opacity-100 translate-y-0 scale-100"
          leave-to="opacity-0 translate-y-4 scale-95"
        >
          <DialogPanel class="panel">
            <DialogTitle class="title">{{ title }}</DialogTitle>
            <p class="description">{{ description }}</p>
            <div class="actions">
              <button
                data-testid="confirm-dialog-cancel"
                type="button"
                class="cancel"
                :disabled="loading"
                @click="close"
              >
                {{ cancelText }}
              </button>
              <button
                data-testid="confirm-dialog-confirm"
                type="button"
                class="confirm"
                :disabled="loading"
                @click="onConfirm"
              >
                {{ loading ? '处理中...' : confirmText }}
              </button>
            </div>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<style scoped>
.confirm-dialog {
  position: fixed;
  inset: 0;
  z-index: 1200;
  isolation: isolate;

  .overlay {
    position: fixed;
    inset: 0;
    z-index: 0;
    background: rgba(42, 31, 112, 0.38);
    backdrop-filter: blur(3px);
  }

  .dialog-wrap {
    position: fixed;
    inset: 0;
    z-index: 1;
    display: grid;
    place-items: center;
    padding: 18px;
  }

  .panel {
    width: min(420px, 100%);
    border-radius: 16px;
    border: 1px solid #9d95d8;
    background: #fff;
    padding: 18px;
    box-shadow: 0 22px 42px rgba(35, 22, 110, 0.28);
    display: grid;
    gap: 12px;

    .title {
      margin: 0;
      color: #1f1b59;
      font: 700 22px/1.2 'Noto Serif SC', serif;
    }

    .description {
      margin: 0;
      color: #514a86;
      line-height: 1.5;
    }

    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
  }
}

button {
  border: 0;
  border-radius: 10px;
  padding: 10px 14px;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.2s ease, opacity 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &.cancel {
    color: #312a61;
    background: #ece9ff;
  }

  &.confirm {
    color: #fff;
    background: linear-gradient(130deg, #2c2a85, #e145a4);
  }
}
</style>
