<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'

const openModel = defineModel<boolean>('open', {
  default: false,
})

const props = withDefaults(
  defineProps<{
    title: string
    description: string
    errorMessage?: string
    loading?: boolean
    confirmText?: string
    cancelText?: string
  }>(),
  {
    errorMessage: '',
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
            <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
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
:global(.confirm-dialog) {
  position: fixed;
  inset: 0;
  z-index: 1200;
  isolation: isolate;

}

.confirm-dialog {
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 0;
    background: rgba(37, 41, 35, 0.42);
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
    max-height: calc(100dvh - 36px);
    overflow-y: auto;
    border-radius: 12px;
    border: 1px solid #dedfd5;
    background: #f7f6f2;
    padding: 24px;
    box-shadow: 0 22px 48px rgba(37, 41, 35, 0.22);
    display: grid;
    gap: 12px;

    .title {
      margin: 0;
      color: #252923;
      font: 700 22px/1.2 'Noto Serif SC', serif;
    }

    .description {
      margin: 0;
      color: #76796f;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }

    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
  }
}

.error { color: #9a3e32; font-size: 13px; line-height: 1.6; }
button {
  border: 1px solid #dedfd5;
  border-radius: 9px;
  padding: 10px 14px;
  cursor: pointer;
  font-weight: 600;
  transition: border-color .16s ease, opacity .16s ease;

  &:hover:not(:disabled) {
    border-color: #aeb3a6;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &.cancel {
    color: #4d5149;
    background: #fffefa;
  }

  &.confirm {
    border-color: #556348;
    color: #fffefa;
    background: #556348;
  }
}
</style>
