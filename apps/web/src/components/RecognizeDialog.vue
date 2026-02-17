<script setup lang="ts">
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'

import UploadField from './UploadField.vue'

const openModel = defineModel<boolean>('open', {
  default: false,
})

const fileModel = defineModel<File | null>('file', {
  default: null,
})

const props = withDefaults(
  defineProps<{
    loading?: boolean
    errorMessage?: string
    statusMessage?: string
  }>(),
  {
    loading: false,
    errorMessage: '',
    statusMessage: '',
  },
)

const emit = defineEmits<{
  submit: []
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

function onSubmit() {
  emit('submit')
}
</script>

<template>
  <TransitionRoot :show="openModel" as="template">
    <Dialog class="recognize-dialog" @close="close">
      <TransitionChild
        as="template"
        enter="ease-out duration-240"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-180"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="overlay" />
      </TransitionChild>

      <div class="dialog-wrap">
        <TransitionChild
          as="template"
          enter="ease-out duration-240"
          enter-from="opacity-0 translate-y-6 scale-95"
          enter-to="opacity-100 translate-y-0 scale-100"
          leave="ease-in duration-180"
          leave-from="opacity-100 translate-y-0 scale-100"
          leave-to="opacity-0 translate-y-4 scale-95"
        >
          <DialogPanel data-testid="recognize-dialog" class="panel">
            <DialogTitle class="title">上传并识别乐谱</DialogTitle>
            <p class="description">识别期间保持弹窗开启，可持续观察状态并替换文件重试。</p>

            <form class="content" @submit.prevent="onSubmit">
              <UploadField v-model:file="fileModel" />

              <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
              <p v-if="statusMessage" class="status">{{ statusMessage }}</p>

              <div class="actions">
                <button
                  data-testid="recognize-dialog-close"
                  type="button"
                  class="ghost"
                  :disabled="loading"
                  @click="close"
                >
                  关闭
                </button>
                <button data-testid="recognize-submit" type="submit" class="primary" :disabled="loading">
                  {{ loading ? '识别中...' : '开始识别' }}
                </button>
              </div>
            </form>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>

<style scoped>
.recognize-dialog {
  position: relative;
  z-index: 30;

  .overlay {
    position: fixed;
    inset: 0;
    background:
      radial-gradient(circle at 10% 18%, rgba(19, 182, 255, 0.22), transparent 45%),
      radial-gradient(circle at 82% 90%, rgba(246, 88, 184, 0.2), transparent 48%),
      rgba(26, 21, 74, 0.5);
    backdrop-filter: blur(4px);
  }

  .dialog-wrap {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 24px 16px;
  }

  .panel {
    width: min(560px, 100%);
    border: 1px solid #8f8ad2;
    border-radius: 18px;
    background: linear-gradient(160deg, #fffdff, #f7f4ff 70%, #eef2ff);
    box-shadow: 0 30px 64px rgba(44, 31, 126, 0.35);
    padding: 22px;
    display: grid;
    gap: 12px;

    .title {
      margin: 0;
      color: #1d1958;
      font: 700 30px/1.1 'Noto Serif SC', serif;
    }

    .description {
      margin: 0;
      color: #5e5998;
      line-height: 1.5;
    }

    .content {
      display: grid;
      gap: 12px;
    }

    .error {
      margin: 0;
      color: #8f184f;
      font-weight: 600;
    }

    .status {
      margin: 0;
      color: #2a2582;
      font-weight: 600;
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
  border-radius: 12px;
  padding: 11px 16px;
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

  &.ghost {
    color: #332d69;
    background: #e8e4ff;
  }

  &.primary {
    color: #fff;
    background: linear-gradient(130deg, #262178, #e249a7);
  }
}
</style>
