<script setup lang="ts">
import { ref } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionChild, TransitionRoot } from '@headlessui/vue'

import UploadField from './UploadField.vue'

const openModel = defineModel<boolean>('open', {
  default: false,
})

const filesModel = defineModel<File[]>('files', {
  default: () => [],
})

const props = withDefaults(
  defineProps<{
    loading?: boolean
    uploadProgress?: number | null
    errorMessage?: string
    statusMessage?: string
  }>(),
  {
    loading: false,
    uploadProgress: null,
    errorMessage: '',
    statusMessage: '',
  },
)

const forceRecognition = ref(false)

const emit = defineEmits<{
  submit: [force: boolean]
}>()

function forceClose() {
  if (props.loading) {
    return
  }
  if (!openModel.value) {
    return
  }
  openModel.value = false
}

function closeByButton() {
  if (props.loading) {
    return
  }
  forceClose()
}

function onSubmit() {
  emit('submit', forceRecognition.value)
}
</script>

<template>
  <TransitionRoot :show="openModel" as="template">
    <Dialog class="recognize-dialog" @close="forceClose">
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
            <div class="eyebrow">导入乐谱</div>
            <DialogTitle class="title">把纸面乐谱变成可播放音符</DialogTitle>
            <p class="description">多页图片会按文件名顺序合为一首乐曲；PDF 读取首页。选好文件后即可开始识别。</p>

            <form class="content" @submit.prevent="onSubmit">
              <UploadField v-model:files="filesModel" :disabled="loading" />

              <label class="description"><input v-model="forceRecognition" type="checkbox" :disabled="loading" /> 已导入过也重新识别（原结果会备份）</label>
              <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
              <div v-if="loading" class="progress" role="status" aria-live="polite">
                <div class="progress-label"><span>导入进度</span><span v-if="uploadProgress !== null">{{ uploadProgress }}%</span><span v-else>处理中</span></div>
                <div class="progress-track" role="progressbar" aria-label="乐谱导入进度" :aria-valuenow="uploadProgress ?? undefined" :aria-valuemin="0" :aria-valuemax="100" :aria-valuetext="uploadProgress === null ? statusMessage : `已上传 ${uploadProgress}%`">
                  <span :class="{ determinate: uploadProgress !== null }" :style="uploadProgress !== null ? { width: `${uploadProgress}%` } : undefined" />
                </div>
                <span>{{ statusMessage || '正在识别，请稍候…' }}</span>
              </div>
              <p v-else-if="statusMessage" class="status" role="status">{{ statusMessage }}</p>

              <div class="actions">
                <button
                  data-testid="recognize-dialog-close"
                  type="button"
                  class="ghost"
                  :disabled="loading"
                  @click="closeByButton"
                >
                  取消
                </button>
                <button data-testid="recognize-submit" type="submit" class="primary" :disabled="loading || !filesModel.length">
                  {{ loading ? '导入中…' : '开始识别' }}
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
:global(.recognize-dialog) {
  position: fixed;
  inset: 0;
  z-index: 1100;
  isolation: isolate;

}

.recognize-dialog {
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
    padding: 24px 16px;
  }

  .panel {
    width: min(580px, 100%);
    max-height: calc(100dvh - 48px);
    overflow-y: auto;
    border: 1px solid #dedfd5;
    border-radius: 12px;
    background: #f7f6f2;
    box-shadow: 0 24px 64px rgba(37, 41, 35, 0.22);
    padding: 30px;
    display: grid;
    gap: 10px;

    .eyebrow { color: #556348; font-size: 11px; font-weight: 700; letter-spacing: .14em; }

    .title {
      margin: 0;
      color: #252923;
      font: 600 25px/1.4 'Songti SC', 'STSong', serif;
    }

    .description {
      margin: 0;
      color: #76796f;
      line-height: 1.65;
      font-size: 13px;
    }

    .content {
      display: grid;
      gap: 16px;
      margin-top: 10px;
    }

    .error {
      margin: 0;
      color: #9a3e32;
      font-weight: 600;
    }

    .status {
      margin: 0;
      color: #556348;
      font-weight: 600;
    }

    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      padding-top: 4px;
    }
  }
}

.progress { display: grid; gap: 7px; color: #556348; font-size: 13px; font-weight: 600; }
.progress-label { display: flex; justify-content: space-between; }
.progress-track { height: 8px; overflow: hidden; border-radius: 3px; background: #dedfd5; }
.progress-track span { display: block; width: 34%; height: 100%; background: #556348; animation: travel 1.25s ease-in-out infinite; }
.progress-track span.determinate { animation: none; transition: width .2s ease; }
@keyframes travel { from { transform: translateX(-110%); } to { transform: translateX(300%); } }

button {
  border: 1px solid #dedfd5;
  border-radius: 9px;
  padding: 11px 16px;
  cursor: pointer;
  font-weight: 600;
  transition: border-color .16s ease, background .16s ease, opacity .16s ease;

  &:hover:not(:disabled) {
    border-color: #aeb3a6;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &.ghost {
    color: #4d5149;
    background: #fffefa;
  }

  &.primary {
    border-color: #556348;
    color: #fffefa;
    background: #556348;
  }
}

@media (prefers-reduced-motion: reduce) { .progress-track span { animation: none; width: 100%; opacity: .6; } }
</style>
